"""System B must never call Engineering AI providers."""
from __future__ import annotations

import shutil
from pathlib import Path

import app.acceptance
from conftest import create_record, create_request

FORBIDDEN_IMPORTS = (
    "engineering_ai.providers",
    "engineering_ai.vision",
    "engineering_ai.embeddings",
    "provider_from_env",
    "vision_from_env",
    "embeddings_from_env",
    "openai",
    "anthropic",
    "sentence_transformers",
    "google.generativeai",
    "litellm",
)


def test_acceptance_package_has_no_ai_provider_imports():
    package = Path(app.acceptance.__file__).resolve().parent
    for path in sorted(package.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_IMPORTS:
            assert token not in text, f"{token} referenced in {path}"


def _raise(*args, **kwargs):
    raise AssertionError("Acceptance must not call an AI provider")


def test_create_and_export_do_not_call_ai_providers(client, monkeypatch, tmp_path):
    import app.engineering_ai.embeddings as embeddings
    import app.engineering_ai.providers as providers
    import app.engineering_ai.vision as vision

    monkeypatch.setattr(providers, "provider_from_env", _raise)
    monkeypatch.setattr(vision, "vision_from_env", _raise)
    monkeypatch.setattr(embeddings, "embeddings_from_env", _raise)

    request = create_request(client, number=None)
    assert request["number"]

    record = create_record(client, request["id"], checklist=[])
    assert record["result"] is None
    assert record["status"] == "draft"
    assert record["checklist"]
    assert {item["state"] for item in record["checklist"]} == {"unconfirmed"}

    xlsx = client.post(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/exports",
        json={"kind": "pyc", "format": "xlsx"},
    )
    assert xlsx.status_code == 201, xlsx.text
    assert client.get(xlsx.json()["download_url"]).status_code == 200

    if shutil.which("libreoffice") or shutil.which("soffice"):
        pdf = client.post(
            f"/api/v1/projects/p1/acceptance-requests/{request['id']}/exports",
            json={"kind": "pyc", "format": "pdf"},
        )
        assert pdf.status_code == 201, pdf.text
        download = client.get(pdf.json()["download_url"])
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF")
