"""Replay representative questions against the reviewed page fixtures."""

import json
from pathlib import Path

import pytest

from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument


FIXTURES = Path(__file__).parent / "fixtures" / "component_qa_golden_2026-11-12"


@pytest.fixture()
def reviewed_pages(session_factory):
    with session_factory() as db:
        for kind, pages in (("drawing", (7, 8, 15, 22, 46)), ("specification", (32, 33))):
            doc_id = f"reviewed-{kind}"
            db.add(SourceDocument(
                id=doc_id, project_id="p1", type=kind,
                original_name=f"reviewed-{kind}.pdf", document_key=doc_id,
                original_path=f"/tmp/{doc_id}.pdf", sha256=(kind * 64)[:64],
                status="ready", is_current=True, is_effective=True,
                page_count=max(pages),
            ))
            for number in pages:
                path = (FIXTURES / f"page_{number:03d}.json" if kind == "drawing"
                        else FIXTURES.parent / "procedure_qa_2026-11-12" / f"report_{number:03d}.json")
                item = json.loads(path.read_text(encoding="utf-8"))
                page_id = f"{doc_id}-{number}"
                db.add(DocumentPage(
                    id=page_id, project_id="p1", document_id=doc_id,
                    page_number=number, drawing_number=item["extraction"].get("drawing_number"),
                ))
                db.add(PageExtraction(
                    id=f"extraction-{page_id}", project_id="p1", document_id=doc_id,
                    page_id=page_id, page_number=number, model="manual-visual-review",
                    prompt_version="qa-replay", mode="manual", status="verified",
                    extraction_json=json.dumps(item["extraction"], ensure_ascii=False),
                ))
        db.commit()


@pytest.mark.parametrize("question,expected,page", [
    ("Cọc H77 đục sâu bao nhiêu cm?", "1 cm", 22),
    ("Cọc H77 chiều dài vết nứt bao nhiêu?", "0.2 m", 7),
    ("Cọc H77 diện tích quét keo epoxy bao nhiêu?", "0.304 m2", 22),
    ("Dầm I-30-31 đục sườn sâu bao nhiêu?", "5 cm", 46),
    ("Dầm I-30-31 đục đáy sâu bao nhiêu?", "7 cm", 46),
    ("Cọc F27 thuộc phân đoạn nào?", "1", 8),
])
def test_reviewed_component_question(client, reviewed_pages, question, expected, page):
    response = client.post("/api/v1/projects/p1/ai/chat", json={"message": question})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["no_source"] is False
    assert expected in body["answer"]
    assert any(citation["page_number"] == page for citation in body["citations"])


def test_unknown_component_does_not_borrow_another_component(client, reviewed_pages):
    response = client.post("/api/v1/projects/p1/ai/chat", json={"message": "Cọc Z999 đục sâu bao nhiêu?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["no_source"] is True
    assert not body["citations"]
