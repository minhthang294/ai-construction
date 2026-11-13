import json

from app.engineering_ai.component_search import find_component_facts
from app.engineering_ai.models import DocumentPage, PageExtraction, SourceDocument
from app.engineering_ai.retrieval import _page_extraction_boosts


def _source(db, project, suffix, *, effective=True):
    document = SourceDocument(
        id=f"doc-{suffix}", project_id=project, type="drawing",
        original_name=f"drawing-{suffix}.pdf", document_key=f"drawing-{suffix}",
        original_path=f"/tmp/drawing-{suffix}.pdf", sha256=suffix * 64,
        status="ready", is_effective=effective, page_count=1,
    )
    page = DocumentPage(
        id=f"page-{suffix}", project_id=project, document_id=document.id,
        page_number=1, revision="A",
    )
    db.add_all([document, page])
    return document, page


def _fact(db, document, page, suffix, *, status="verified", code="P-01", group="Nhóm 2"):
    db.add(PageExtraction(
        id=f"fact-{suffix}", project_id=document.project_id,
        document_id=document.id, page_id=page.id, page_number=page.page_number,
        model="test", prompt_version=suffix, mode="direct", status=status,
        extraction_json=json.dumps({"component_facts": [{
            "component_type": "pile", "component_code": code,
            "fact_name": "chiều sâu đục", "value": "1", "unit": "cm",
            "quote": "t = 1 cm", "group": group,
            "segment": "Phân đoạn 1", "location": "Cầu chính",
            "table_row": 2, "table_column": "t",
        }]}),
    ))


def test_component_lookup_filters_project_status_effective_and_group(session_factory):
    with session_factory() as db:
        current, current_page = _source(db, "p1", "a")
        old, old_page = _source(db, "p1", "b", effective=False)
        foreign, foreign_page = _source(db, "p2", "c")
        _fact(db, current, current_page, "a")
        _fact(db, current, current_page, "draft", status="proposed", code="P-02")
        _fact(db, old, old_page, "b", group="Nhóm 3")
        _fact(db, current, old_page, "wrong-page", code="P-03")
        _fact(db, foreign, foreign_page, "c")
        db.commit()

        current_facts = find_component_facts(
            db, "p1", location="cau chinh", segment="1", group="2"
        )
        assert [item.fact["component_code"] for item in current_facts] == ["P-01"]
        assert [item.fact["component_code"] for item in find_component_facts(db, "p1", segment="1")] == ["P-01"]
        assert current_facts[0].table_row == 2
        assert current_facts[0].table_column == "t"
        assert current_facts[0].url.endswith("/documents/doc-a/pages/1")
        assert find_component_facts(db, "p1", component_code="P-02") == []
        assert find_component_facts(db, "p1", component_code="P-03") == []
        assert find_component_facts(db, "p1", group="3", location="Cầu chính", segment="1") == []
        assert len(find_component_facts(db, "p1", group="3", location="Cầu chính", segment="1", scope="history")) == 1
        assert len(find_component_facts(db, "p2", component_code="P-01")) == 1
        assert find_component_facts(db, "p1") == []


def test_unverified_extraction_cannot_boost_retrieval(session_factory):
    with session_factory() as db:
        for status in ("proposed", "verified"):
            db.add(PageExtraction(
                id=f"boost-{status}", project_id="p1", document_id="doc",
                page_id=f"page-{status}", page_number=1, model="test",
                prompt_version=status, mode="direct", status=status,
                extraction_json=json.dumps({"key_values": [
                    {"name": "cọc", "value": "H77", "unit": "cm"}
                ]}),
            ))
        db.commit()
        boosts = _page_extraction_boosts(db, "p1", ["coc", "h77"])
        assert "page-verified" in boosts
        assert "page-proposed" not in boosts
