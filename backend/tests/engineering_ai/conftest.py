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
    project_access,
    project_editor_access,
)
from app.engineering_ai.models import Base, DocumentPage, SourceDocument
from app.engineering_ai.providers import ExtractiveProvider, ProviderAnswer
from app.engineering_ai.router import router


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
def answer_provider():
    return MockAnswerProvider()


@pytest.fixture()
def client(session_factory, answer_provider):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": "test-user"})()
    app.dependency_overrides[project_access] = lambda project_id: None
    app.dependency_overrides[project_editor_access] = lambda project_id: None
    app.dependency_overrides[get_answer_provider] = lambda: answer_provider
    with TestClient(app) as test_client:
        yield test_client


def add_source_document(
    session_factory,
    *,
    project_id="p1",
    suffix="a",
    document_id=None,
    page_numbers=(1, 2),
    effective=True,
    current=True,
    status="ready",
    document_type="drawing",
    original_name=None,
    drawing_number="BV-01",
    revision="A",
    page_rendered=False,
    version=1,
    document_key=None,
    sha256=None,
    original_path=None,
):
    """Seed an existing source document/page set (owner no longer uploads PDFs)."""

    document_id = document_id or f"doc-{suffix}"
    document = SourceDocument(
        id=document_id,
        project_id=project_id,
        type=document_type,
        original_name=original_name or f"drawing-{suffix}.pdf",
        document_key=document_key or f"drawing-{suffix}",
        original_path=original_path or f"/tmp/drawing-{suffix}.pdf",
        sha256=sha256 or (suffix * 64)[:64],
        status=status,
        is_current=current,
        is_effective=effective,
        version=version,
        page_count=len(page_numbers),
        drawing_number=drawing_number,
        revision=revision,
    )
    pages = []
    for number in page_numbers:
        page = DocumentPage(
            id=f"{document_id}-page-{number}",
            project_id=project_id,
            document_id=document_id,
            page_number=number,
            drawing_number=drawing_number,
            revision=revision,
        )
        if page_rendered:
            from app.engineering_ai import storage

            path = storage.page_render_path(project_id, document_id, number)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
                + b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                + b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            page.rendered_path = str(path)
        pages.append(page)
    with session_factory() as db:
        db.add_all([document, *pages])
        page_rows = [
            {"id": page.id, "page_number": page.page_number} for page in pages
        ]
        db.commit()
    return {
        "id": document_id,
        "status": status,
        "page_count": len(page_numbers),
        "pages": page_rows,
    }


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
def digital_document(client, session_factory):
    document = add_source_document(
        session_factory,
        suffix="bv01",
        page_numbers=(1, 2),
        document_type="specification",
        original_name="BV-01.pdf",
    )
    assert document["status"] == "ready"
    return document
