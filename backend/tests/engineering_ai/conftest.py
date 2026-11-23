import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.engineering_ai.dependencies import (
    get_answer_provider,
    get_current_user,
    get_db,
    get_embedding_provider,
    get_max_pages,
    get_ocr_engine,
    get_ocr_languages,
    get_session_factory,
    get_vision_provider,
    project_access,
    project_editor_access,
)
from app.engineering_ai.embeddings import HashingEmbeddingProvider
from app.engineering_ai.models import Base
from app.engineering_ai.ocr import NullOcrEngine, OcrResult
from app.engineering_ai.providers import ExtractiveProvider, ProviderAnswer
from app.engineering_ai.router import router
from app.engineering_ai.vision import NoopVisionProvider


class MockOcrEngine:
    name = "mock-ocr"

    def __init__(self) -> None:
        self.result = OcrResult(text="", confidence=None, engine=self.name)
        self.calls = 0

    def extract_text(self, image_bytes: bytes, languages: str) -> OcrResult:
        self.calls += 1
        return self.result


class MockAnswerProvider:
    name = "mock"

    def __init__(self) -> None:
        self.response = None
        self.calls = []
        self._fallback = ExtractiveProvider()

    def answer(self, question, contexts):
        self.calls.append((question, list(contexts)))
        if self.response is not None:
            return ProviderAnswer(text=self.response)
        return self._fallback.answer(question, contexts)


class MockVisionProvider:
    name = "mock-vision"

    def __init__(self) -> None:
        self.calls = 0
        self.suggestion = None

    def suggest(self, image_bytes, mime_type):
        from app.engineering_ai.vision import VisionSuggestion

        self.calls += 1
        return self.suggestion or VisionSuggestion(
            suggested_category="progress",
            suggested_caption="Khu vực thi công",
            confidence=0.8,
        )


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGINEERING_AI_STORAGE", str(tmp_path / "storage"))
    monkeypatch.setenv("ENGINEERING_AI_RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.delenv("ENGINEERING_AI_PROVIDER", raising=False)
    monkeypatch.delenv("ENGINEERING_AI_API_KEY", raising=False)


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def ocr_engine():
    return MockOcrEngine()


@pytest.fixture()
def answer_provider():
    return MockAnswerProvider()


@pytest.fixture()
def vision_provider():
    return MockVisionProvider()


@pytest.fixture()
def embedding_provider():
    return HashingEmbeddingProvider(64)


@pytest.fixture()
def client(session_factory, ocr_engine, answer_provider, vision_provider, embedding_provider):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "test-user"})()
    app.dependency_overrides[project_access] = lambda project_id: None
    app.dependency_overrides[project_editor_access] = lambda project_id: None
    app.dependency_overrides[get_ocr_engine] = lambda: ocr_engine
    app.dependency_overrides[get_answer_provider] = lambda: answer_provider
    app.dependency_overrides[get_embedding_provider] = lambda: embedding_provider
    app.dependency_overrides[get_vision_provider] = lambda: vision_provider
    app.dependency_overrides[get_max_pages] = lambda: 100
    app.dependency_overrides[get_ocr_languages] = lambda: "vie+eng"
    with TestClient(app) as test_client:
        yield test_client


def make_text_pdf(pages: list[str]) -> bytes:
    import pymupdf

    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    data = document.tobytes()
    document.close()
    return data


def make_scanned_pdf() -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.draw_rect(pymupdf.Rect(60, 60, 500, 700), color=(0, 0, 0), width=2)
    page.draw_line((70, 120), (480, 120), color=(0, 0, 0), width=1)
    data = document.tobytes()
    document.close()
    return data


def upload_pdf(client, project_id="p1", filename="drawing.pdf", data=None):
    payload = data if data is not None else make_text_pdf(["placeholder"])
    return client.post(
        f"/api/v1/projects/{project_id}/documents",
        files=[("file", (filename, payload, "application/pdf"))],
    )


def add_page_extraction(
    session_factory,
    *,
    project_id,
    document_id,
    page_id,
    page_number,
    extraction,
    status="verified",
):
    """Insert one AI page extraction, the source chat answers are allowed to use."""

    import json

    from app.engineering_ai.models import PageExtraction

    with session_factory() as db:
        db.add(
            PageExtraction(
                project_id=project_id,
                document_id=document_id,
                page_id=page_id,
                page_number=page_number,
                model="test",
                prompt_version="test",
                mode="direct",
                status=status,
                confidence=extraction.get("confidence"),
                extraction_json=json.dumps(extraction, ensure_ascii=False),
            )
        )
        db.commit()


def cover_extraction(value="50"):
    return {
        "page_type": "specification",
        "title": "Concrete cover for abutment",
        "drawing_number": "BV-01",
        "revision": "A",
        "summary": f"Lớp bảo vệ bê tông cho mố là {value} mm.",
        "key_values": [
            {
                "name": "concrete cover for abutment",
                "value": value,
                "unit": "mm",
                "quote": f"concrete cover for abutment is {value} mm",
            }
        ],
        "table_rows": [],
        "warnings": [],
        "confidence": 0.9,
    }


@pytest.fixture()
def digital_document(client):
    pdf = make_text_pdf(
        [
            "Drawing No: BV-01 Rev A. Bridge abutment concrete grade C30. "
            "All dimensions in millimetres. Approved by site engineer.",
            "Specification section: concrete cover for abutment is 50 mm. "
            "Reinforcement shall comply with the project specification.",
        ]
    )
    response = upload_pdf(client, filename="BV-01.pdf", data=pdf)
    assert response.status_code == 201, response.text
    return response.json()
