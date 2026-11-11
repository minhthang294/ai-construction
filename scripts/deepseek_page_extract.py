#!/usr/bin/env python3
"""One-time page extraction POC using the DeepSeek V4.1 Flash model.

This script deliberately does not call Codex or any other model.  It renders
pages from a PDF, optionally runs the existing Tesseract OCR baseline, then
asks OpenCode's DeepSeek V4.1 Flash model (image input) for strict JSON.

Output is written under a caller-provided directory; nothing is written to
``data/app.db`` or the application's private storage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pymupdf

SCHEMA = {
    "page_type": "drawing|specification|table|text|other",
    "title": "string|null",
    "drawing_number": "string|null",
    "revision": "string|null",
    "summary": "string",
    "key_values": [
        {"name": "string", "value": "string", "unit": "string|null", "quote": "string"}
    ],
    "table_rows": [["string"]],
    "warnings": ["string"],
    "confidence": "number 0..1",
}

PROMPT = """Bạn đang trích xuất MỘT trang hồ sơ công trình để làm kho tri thức.

Hãy đọc ảnh trang đính kèm và chỉ ghi lại thông tin NHÌN THẤY. Không suy đoán, không bịa số liệu, không dùng kiến thức bên ngoài. Không gọi bất kỳ tool nào, không đọc file khác; chỉ dùng ảnh đính kèm.

Trả về DUY NHẤT một JSON object, không markdown, không giải thích, đúng cấu trúc sau:
{
  "page_type": "drawing" | "specification" | "table" | "text" | "other",
  "title": string | null,
  "drawing_number": string | null,
  "revision": string | null,
  "summary": string,
  "key_values": [
    {"name": string, "value": string, "unit": string | null, "quote": string}
  ],
  "table_rows": [[string]],
  "warnings": [string],
  "confidence": number
}

Quy tắc:
- `quote` phải là chuỗi nhìn thấy nguyên văn trên trang.
- Chỉ đưa vào `key_values` các thông số kỹ thuật nhìn thấy rõ; nếu không chắc, thêm warning và giảm confidence.
- Không tự tạo tên người, chữ ký, số hiệu bản vẽ, revision hoặc kích thước.
- Nếu trang là bìa/danh mục, dùng page_type "text" hoặc "other".
- Nếu trang có bảng, đưa các hàng nhìn thấy vào `table_rows` (tối đa 50 hàng).
- `confidence` là mức tin cậy của bạn vào toàn bộ kết quả, từ 0 đến 1.
"""

PROMPT_AGENT = PROMPT.replace(
    "Không gọi bất kỳ tool nào, không đọc file khác; chỉ dùng ảnh đính kèm.",
    "Được phép dùng tool để đọc/crop chính ảnh đính kèm khi cần nhìn rõ chi tiết; không đọc file ngoài ảnh.",
)


def _parse_pages(value: str) -> list[int]:
    pages: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


def _render(pdf: Path, page_number: int, out_dir: Path, dpi: int) -> Path:
    document = pymupdf.open(pdf)
    try:
        if page_number < 1 or page_number > document.page_count:
            raise ValueError(f"page {page_number} outside 1..{document.page_count}")
        page = document.load_page(page_number - 1)
        pix = page.get_pixmap(dpi=dpi)
        path = out_dir / f"{pdf.stem[:40]}-p{page_number:04d}.png"
        pix.save(path)
        return path
    finally:
        document.close()


def _ocr(image: Path, languages: str) -> dict[str, Any]:
    started = time.time()
    env = dict(os.environ)
    if "TESSDATA_PREFIX" not in env:
        candidate = Path.home() / ".local/share/tessdata"
        if (candidate / "vie.traineddata").is_file():
            env["TESSDATA_PREFIX"] = str(candidate)
    try:
        result = subprocess.run(
            ["tesseract", str(image), "stdout", "-l", languages, "--psm", "3", "tsv"],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        words = 0
        confidences: list[float] = []
        for line in result.stdout.splitlines()[1:]:
            cols = line.split("\t")
            if len(cols) < 12 or not cols[11].strip():
                continue
            try:
                confidence = float(cols[10])
            except ValueError:
                continue
            if confidence >= 0:
                words += 1
                confidences.append(confidence)
        return {
            "engine": "tesseract",
            "languages": languages,
            "words": words,
            "mean_confidence": round(sum(confidences) / len(confidences), 4)
            if confidences
            else None,
            "seconds": round(time.time() - started, 2),
            "exit": result.returncode,
            "stderr": result.stderr[-500:],
        }
    except Exception as exc:  # noqa: BLE001 - POC records the failure
        return {"engine": "tesseract", "error": str(exc), "seconds": round(time.time() - started, 2)}


def _api(method: str, path: str, body: dict[str, Any] | None = None, timeout: int = 120) -> Any:
    command = ["opencode", "api", method, path]
    if body is not None:
        command.extend(["-d", json.dumps(body, ensure_ascii=False)])
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"opencode api {method} {path} failed: {result.stderr[-800:] or result.stdout[-800:]}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else None


def _run_deepseek(image: Path, model: str, _workdir: Path, timeout: int) -> dict[str, Any]:
    """Send the image as a direct attachment, not through an agent tool loop.

    This is the fast path: the model receives the page image as content, so it
    does not need shell/read/crop tools.  It still uses only the requested
    DeepSeek model.
    """

    started = time.time()
    provider, _, model_id = model.partition("/")
    if not provider or not model_id:
        raise ValueError("--model must look like provider/model")
    session = _api(
        "POST",
        "/api/session",
        {
            "title": f"Page extraction {image.name}",
            "model": {"id": model_id, "providerID": provider},
        },
    )["data"]
    session_id = session["id"]
    try:
        _api(
            "POST",
            f"/api/session/{session_id}/prompt",
            {
                "text": PROMPT,
                "files": [
                    {
                        "uri": f"file://{image.resolve()}",
                        "name": image.name,
                        "description": "Trang hồ sơ cần trích xuất",
                    }
                ],
            },
        )
        _api(
            "POST",
            f"/api/experimental/session/{session_id}/wait",
            timeout=timeout,
        )
        messages = _api("GET", f"/api/session/{session_id}/message")["data"]
        texts: list[str] = []
        for message in messages:
            if message.get("type") != "assistant":
                continue
            for part in message.get("content") or []:
                if part.get("type") == "text" and part.get("text"):
                    texts.append(part["text"])
        info = _api("GET", f"/api/session/{session_id}")["data"]
        tokens = info.get("tokens") or {}
        cache = tokens.get("cache") or {}
        return {
            "mode": "direct-image-api",
            "session_id": session_id,
            "exec_exit": 0,
            "seconds": round(time.time() - started, 2),
            "text": "\n".join(texts).strip(),
            "tokens": {
                "input": int(tokens.get("input") or 0),
                "output": int(tokens.get("output") or 0),
                "reasoning": int(tokens.get("reasoning") or 0),
                "cache_read": int(cache.get("read") or 0),
            },
            "cost": info.get("cost"),
            "errors": [],
        }
    finally:
        try:
            _api("DELETE", f"/api/session/{session_id}")
        except Exception:  # noqa: BLE001 - cleanup is best-effort
            pass


def _run_deepseek_agent(image: Path, model: str, workdir: Path, timeout: int) -> dict[str, Any]:
    """Slow comparison path: agent may use read/crop tools on the page image."""

    started = time.time()
    command = [
        "opencode",
        "run",
        "--model",
        model,
        "--format",
        "json",
        "--archived",
        "--file",
        str(image),
        PROMPT_AGENT,
    ]
    result = subprocess.run(
        command, cwd=workdir, capture_output=True, text=True, timeout=timeout
    )
    texts: list[str] = []
    tokens = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0}
    errors: list[str] = []
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            text = (event.get("part") or {}).get("text")
            if text:
                texts.append(text)
        if event.get("type") == "step_finish":
            usage = (event.get("part") or {}).get("tokens") or {}
            tokens["input"] += int(usage.get("input") or 0)
            tokens["output"] += int(usage.get("output") or 0)
            tokens["reasoning"] += int(usage.get("reasoning") or 0)
            cache = usage.get("cache") or {}
            tokens["cache_read"] += int(cache.get("read") or 0)
        if event.get("type") == "error":
            error = event.get("error") or {}
            errors.append(str(error.get("message") or error))
    return {
        "mode": "agent-tool-api",
        "exec_exit": result.returncode,
        "seconds": round(time.time() - started, 2),
        "text": "\n".join(texts).strip(),
        "tokens": tokens,
        "errors": errors,
    }


def _parse_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value, None
        return None, "top-level JSON is not an object"
    except json.JSONDecodeError as exc:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(cleaned[start : end + 1])
                if isinstance(value, dict):
                    return value, None
            except json.JSONDecodeError:
                pass
        return None, str(exc)


def _validate(value: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    required = {
        "page_type",
        "title",
        "drawing_number",
        "revision",
        "summary",
        "key_values",
        "table_rows",
        "warnings",
        "confidence",
    }
    missing = sorted(required - set(value))
    if missing:
        problems.append(f"missing fields: {missing}")
    if value.get("page_type") not in {
        "drawing",
        "specification",
        "table",
        "text",
        "other",
    }:
        problems.append("invalid page_type")
    if not isinstance(value.get("summary"), str) or not value.get("summary", "").strip():
        problems.append("summary is empty")
    if not isinstance(value.get("key_values"), list):
        problems.append("key_values is not a list")
    else:
        for index, item in enumerate(value["key_values"]):
            if not isinstance(item, dict):
                problems.append(f"key_values[{index}] is not an object")
                continue
            if not all(key in item for key in ("name", "value", "unit", "quote")):
                problems.append(f"key_values[{index}] missing keys")
    if not isinstance(value.get("table_rows"), list):
        problems.append("table_rows is not a list")
    if not isinstance(value.get("warnings"), list):
        problems.append("warnings is not a list")
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        problems.append("confidence is not a number in 0..1")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pages", required=True, help="1-based pages, e.g. 3,6,10 or 5-8")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="opencode-go/deepseek-v4.1-flash")
    parser.add_argument(
        "--mode",
        choices=("direct", "agent"),
        default="direct",
        help="direct: image attachment, fast; agent: read/crop tools, slower but more detailed",
    )
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--ocr-languages", default="vie+eng")
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    pages_dir = args.out / "pages"
    results_dir = args.out / "results"
    pages_dir.mkdir(exist_ok=True)
    results_dir.mkdir(exist_ok=True)
    workdir = args.out / "workdir"
    workdir.mkdir(exist_ok=True)
    (workdir / "schema.json").write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2))

    manifest: dict[str, Any] = {
        "pdf": str(args.pdf),
        "model": args.model,
        "mode": args.mode,
        "dpi": args.dpi,
        "pages": [],
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    for page_number in _parse_pages(args.pages):
        entry: dict[str, Any] = {"page": page_number, "status": "pending"}
        print(f"[page {page_number}] render", flush=True)
        try:
            image = _render(args.pdf, page_number, pages_dir, args.dpi)
            entry["image"] = str(image)
            entry["image_bytes"] = image.stat().st_size
            if not args.skip_ocr:
                print(f"[page {page_number}] OCR baseline", flush=True)
                entry["ocr"] = _ocr(image, args.ocr_languages)
            print(f"[page {page_number}] DeepSeek V4.1 Flash ({args.mode})", flush=True)
            if args.mode == "agent":
                model_result = _run_deepseek_agent(
                    image, args.model, workdir, args.timeout
                )
            else:
                model_result = _run_deepseek(image, args.model, workdir, args.timeout)
            entry["model"] = {
                key: value
                for key, value in model_result.items()
                if key not in {"text", "stdout_tail", "stderr_tail"}
            }
            raw = model_result.get("text") or ""
            raw_path = results_dir / f"page-{page_number:04d}.raw.txt"
            raw_path.write_text(raw)
            entry["raw_text"] = str(raw_path)
            value, parse_error = _parse_json(raw)
            if value is None:
                entry["status"] = "invalid_json"
                entry["parse_error"] = parse_error
            else:
                problems = _validate(value)
                entry["status"] = "ok" if not problems else "invalid_schema"
                entry["validation"] = problems
                json_path = results_dir / f"page-{page_number:04d}.json"
                json_path.write_text(json.dumps(value, ensure_ascii=False, indent=2))
                entry["result"] = str(json_path)
                entry["page_type"] = value.get("page_type")
                entry["summary"] = value.get("summary")
                entry["confidence"] = value.get("confidence")
                entry["key_value_count"] = len(value.get("key_values") or [])
                entry["warning_count"] = len(value.get("warnings") or [])
        except Exception as exc:  # noqa: BLE001 - POC keeps going
            entry["status"] = "error"
            entry["error"] = str(exc)
        manifest["pages"].append(entry)
        print(f"[page {page_number}] {entry['status']}", flush=True)

    manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    print(f"manifest: {args.out / 'manifest.json'}")
    return 0 if all(item["status"] in {"ok", "invalid_schema", "invalid_json"} for item in manifest["pages"]) else 1


if __name__ == "__main__":
    sys.exit(main())
