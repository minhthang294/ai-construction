#!/usr/bin/env python3
"""Import page-extraction JSON files from POC/batch runs into the app.

The app must be running and the source documents already ingested.  The script
only sends extraction metadata; it never writes page text or originals.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _auth(base_url: str, password_file: Path) -> tuple[httpx.Client, dict[str, str]]:
    values = dict(
        line.strip().split("=", 1)
        for line in password_file.read_text().splitlines()
        if "=" in line
    )
    client = httpx.Client(base_url=base_url, timeout=180)
    response = client.post(
        "/auth/login",
        json={"username": values["username"], "password": values["password"]},
    )
    response.raise_for_status()
    return client, {"Authorization": f"Bearer {response.json()['access_token']}"}


def _project(client: httpx.Client, headers: dict[str, str], marker: str | None) -> dict:
    projects = client.get("/projects", headers=headers).json()
    if marker:
        for project in projects:
            if marker.casefold() in project["name"].casefold():
                return project
    if len(projects) == 1:
        return projects[0]
    raise SystemExit("Pass --project with part of the project name")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765/api/v1")
    parser.add_argument(
        "--password-file",
        type=Path,
        default=ROOT / "data/.admin-initial-password",
    )
    parser.add_argument("--project", default="DAP")
    parser.add_argument("--prompt-version", default="batch-v1")
    args = parser.parse_args()

    client, headers = _auth(args.base_url, args.password_file)
    project = _project(client, headers, args.project)
    base = f"/projects/{project['id']}"
    documents = client.get(f"{base}/documents", headers=headers).json()
    by_name = {document["original_name"]: document for document in documents}
    imported = 0
    errors = 0
    seen_pages: set[tuple[str, int]] = set()

    for run_dir in args.runs:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            print("skip missing manifest", run_dir)
            continue
        manifest = json.loads(manifest_path.read_text())
        pdf_name = Path(manifest.get("pdf", "")).name
        document = by_name.get(pdf_name)
        if document is None:
            print("skip unknown document", pdf_name)
            errors += 1
            continue
        page_ids = {
            page["page_number"]: page["id"] for page in document.get("pages", [])
        }
        if not page_ids:
            full = client.get(
                f"{base}/documents/{document['id']}", headers=headers
            ).json()
            page_ids = {
                page["page_number"]: page["id"] for page in full.get("pages", [])
            }
        for entry in manifest.get("pages") or []:
            result_path = entry.get("result")
            if not result_path or entry.get("status") not in {"ok", "invalid_schema"}:
                continue
            page_number = entry["page"]
            key = (document["id"], page_number)
            if key in seen_pages:
                continue
            seen_pages.add(key)
            try:
                extraction = json.loads(Path(result_path).read_text())
            except Exception as exc:  # noqa: BLE001
                print("bad JSON", result_path, exc)
                errors += 1
                continue
            if page_number not in page_ids:
                print("missing page", pdf_name, page_number)
                errors += 1
                continue
            payload = {
                "model": manifest.get(
                    "model", "opencode-go/deepseek-v4.1-flash"
                ),
                "prompt_version": args.prompt_version,
                "mode": "tile" if entry.get("tile_count") else "direct",
                "extraction": extraction,
                "confidence": extraction.get("confidence"),
                "warnings": extraction.get("warnings") or [],
            }
            response = client.post(
                f"{base}/documents/{document['id']}/pages/{page_number}/extractions",
                headers=headers,
                json=payload,
            )
            if response.status_code not in (200, 201):
                print(
                    "error",
                    pdf_name,
                    page_number,
                    response.status_code,
                    response.text[:300],
                )
                errors += 1
                continue
            imported += 1
    print(json.dumps({"imported": imported, "errors": errors}, ensure_ascii=False))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
