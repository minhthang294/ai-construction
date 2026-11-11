"""System B must never call Engineering AI providers or page-extraction POCs."""
from __future__ import annotations

import shutil
import sys
import types
from pathlib import Path

import app.acceptance
from conftest import create_record, create_request

FORBIDDEN_IMPORTS = (
    "engineering_ai.providers",
    "engineering_ai.vision",
    "engineering_ai.embeddings",
    "engineering_ai.page_extraction",
    "page_extraction",
    "deepseek_page_extract",
    "provider_from_env",
    "vision_from_env",
    "embeddings_from_env",
    "page_extraction_from_env",
    "openai",
    "anthropic",
    "sentence_transformers",
    "google.generativeai",
    "gemini",
    "litellm",
    "ollama",
    "mistralai",
    "transformers",
    "torch",
)


def test_acceptance_package_has_no_ai_provider_imports():
    package = Path(app.acceptance.__file__).resolve().parent
    for path in sorted(package.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_IMPORTS:
            assert token not in text, f"{token} referenced in {path}"


def _raise(*args, **kwargs):
    raise AssertionError("Acceptance must not call an AI provider")


def test_deepseek_page_extraction_poc_is_not_imported_or_invoked(client, monkeypatch):
    package = Path(app.acceptance.__file__).resolve().parent
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(package.rglob("*.py"))
    ).lower()
    assert "page_extraction" not in source
    assert "deepseek" not in source
    assert "engineering_ai.page_extraction" not in source

    def blocked(*args, **kwargs):
        raise AssertionError("POC page extraction must not be invoked by acceptance")

    fake = types.ModuleType("app.engineering_ai.page_extraction")
    fake.__getattr__ = lambda name: blocked
    fake.extract_page = blocked
    fake.extract_page_with_model = blocked
    fake.page_extraction_from_env = blocked
    monkeypatch.setitem(sys.modules, "app.engineering_ai.page_extraction", fake)

    request = create_request(client, number=None)
    record = create_record(client, request["id"], checklist=[])
    assert record["result"] is None
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
        assert client.get(pdf.json()["download_url"]).status_code == 200


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
