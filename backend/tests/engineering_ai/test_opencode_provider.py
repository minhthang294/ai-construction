import subprocess

import pytest

from app.engineering_ai import providers
from app.engineering_ai.constants import NO_SOURCE_ANSWER
from app.engineering_ai.providers import (
    ExtractiveProvider,
    OpenCodeDeepSeekProvider,
    ProviderError,
    SourceContext,
    provider_from_env,
)


def _context():
    return SourceContext(
        index=1,
        text="Lớp bảo vệ bê tông 50 mm.",
        document_name="BV-01.pdf",
        version=1,
        page_number=2,
        drawing_number="BV-01",
        revision="A",
    )


def test_opencode_provider_success_sends_grounded_prompt_and_deletes_session(monkeypatch):
    calls = []

    def fake_call(method, path, body=None, timeout=120):
        calls.append({"method": method, "path": path, "body": body, "timeout": timeout})
        if path == "/api/session":
            return {"data": {"id": "session-1"}}
        if path == "/api/session/session-1/prompt":
            return {"data": {}}
        if path == "/api/experimental/session/session-1/wait":
            return {"data": {}}
        if path == "/api/session/session-1/message":
            return {
                "data": [
                    {
                        "type": "assistant",
                        "content": [
                            {"type": "text", "text": "Theo [1], lớp bảo vệ là 50 mm."}
                        ],
                    }
                ]
            }
        if method == "DELETE" and path == "/api/session/session-1":
            return {"data": {}}
        raise AssertionError(f"unexpected call {method} {path}")

    monkeypatch.setattr(providers, "_opencode_call", fake_call)
    provider = OpenCodeDeepSeekProvider(timeout=7)
    assert provider.name == "opencode_deepseek:deepseek-v4.1-flash"
    answer = provider.answer("Lớp bảo vệ là bao nhiêu?", [_context()])
    assert answer.text == "Theo [1], lớp bảo vệ là 50 mm."
    assert [call["method"] for call in calls] == ["POST", "POST", "POST", "GET", "DELETE"]
    session_body = calls[0]["body"]
    assert session_body["title"] == "Construction AI answer"
    assert session_body["model"] == {
        "providerID": "opencode-go",
        "id": "deepseek-v4.1-flash",
    }
    prompt_text = calls[1]["body"]["text"]
    assert calls[1]["body"]["files"] == []
    assert "Không gọi tool; chỉ trả lời từ nguồn." in prompt_text
    assert NO_SOURCE_ANSWER in prompt_text
    assert "NGUỒN:" in prompt_text
    assert "Lớp bảo vệ bê tông 50 mm." in prompt_text
    assert all(call["timeout"] == 7 for call in calls[:4])


def test_opencode_provider_error_degrades_to_extracted_data(monkeypatch, session_factory):
    def failing_call(*args, **kwargs):
        raise ProviderError("opencode request timed out")

    monkeypatch.setattr(providers, "_opencode_call", failing_call)
    provider = OpenCodeDeepSeekProvider()
    with pytest.raises(ProviderError):
        provider.answer("Lớp bảo vệ?", [_context()])

    from app.engineering_ai.database_chat import answer_structured_question
    from app.engineering_ai.models import DocumentPage, SourceDocument

    from .conftest import add_page_extraction, cover_extraction

    with session_factory() as db:
        db.add(
            SourceDocument(
                id="doc-1",
                project_id="p1",
                type="specification",
                original_name="BV-01.pdf",
                document_key="bv-01",
                original_path="/tmp/BV-01.pdf",
                sha256="a" * 64,
                status="ready",
                is_current=True,
                is_effective=True,
                page_count=1,
                drawing_number="BV-01",
                revision="A",
            )
        )
        db.add(
            DocumentPage(
                id="page-1",
                project_id="p1",
                document_id="doc-1",
                page_number=2,
                drawing_number="BV-01",
                revision="A",
            )
        )
        db.commit()
    add_page_extraction(
        session_factory,
        project_id="p1",
        document_id="doc-1",
        page_id="page-1",
        page_number=2,
        extraction={**cover_extraction(), "title": "Lớp bảo vệ bê tông"},
    )

    class FailingProvider:
        name = "failing"

        def answer(self, question, contexts):
            raise ProviderError("timeout")

    with session_factory() as db:
        answer, citations, warnings, no_source, _confidence = answer_structured_question(
            db, "p1", "Lớp bảo vệ bê tông là bao nhiêu?", 6, FailingProvider()
        )
    assert "Dữ kiện AI trích xuất" in answer.text
    assert no_source is False
    assert citations
    assert any("AI provider không khả dụng" in warning for warning in warnings)


def test_opencode_call_timeout_is_provider_error(monkeypatch):
    def timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(["opencode"], 1)

    monkeypatch.setattr(providers.subprocess, "run", timeout_run)
    with pytest.raises(ProviderError):
        providers._opencode_call("GET", "/api/session/x/message", timeout=1)


def test_opencode_call_allows_empty_204(monkeypatch):
    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(providers.subprocess, "run", lambda *args, **kwargs: Completed())
    assert providers._opencode_call("POST", "/api/experimental/session/x/wait") is None


def test_provider_from_env_aliases_and_model_allow_list(monkeypatch):
    for alias in ("opencode_deepseek", "opencode", "deepseek"):
        monkeypatch.setenv("ENGINEERING_AI_PROVIDER", alias)
        monkeypatch.delenv("ENGINEERING_AI_OPENCODE_MODEL", raising=False)
        provider = provider_from_env()
        assert isinstance(provider, OpenCodeDeepSeekProvider)
        assert provider.name == "opencode_deepseek:deepseek-v4.1-flash"

    monkeypatch.setenv("ENGINEERING_AI_OPENCODE_MODEL", "other/provider")
    assert isinstance(provider_from_env(), ExtractiveProvider)
