"""Read-only checks for the visual-confirmed component QA golden fixture.

No database, no product imports, no writes. Codex owns replay/import.
"""

import json
from pathlib import Path

FIXTURE_DIR = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "component_qa_golden_2026-11-12"
)


def _load(page_number: int) -> dict:
    path = FIXTURE_DIR / f"page_{page_number:03d}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _facts(page_number: int) -> list[dict]:
    return _load(page_number)["extraction"]["component_facts"]


def _segment_one_codes(page_number: int, group: str) -> list[str]:
    return [
        fact["component_code"]
        for fact in _facts(page_number)
        if fact["group"] == group and fact["segment"] == "1"
    ]


def test_group_2_segment_1_has_45_unique_pile_codes():
    codes = _segment_one_codes(8, "2")
    assert len(codes) == 45
    assert len(set(codes)) == 45
    assert codes[0] == "I3"
    assert codes[-1] == "D151"


def test_group_3_segment_1_has_39_unique_pile_codes_and_excludes_i49():
    codes = _segment_one_codes(15, "3")
    assert len(codes) == 39
    assert len(set(codes)) == 39
    assert codes[0] == "I6"
    assert codes[-1] == "A150"
    assert "I49" not in codes

    group_2 = set(_segment_one_codes(8, "2"))
    group_3 = set(codes)
    assert group_2.isdisjoint(group_3)
    assert len(group_2 | group_3) == 84

    excluded = _load(15)["evidence"]["excluded_rows"]
    assert excluded == [
        {
            "component_code": "I49",
            "segment": "2",
            "reason": (
                "Đường kẻ ngang của ô gộp Phân đoạn 1 nằm ngay trên I49; "
                "I49 là dòng đầu Phân đoạn 2."
            ),
            "evidence_crop": "p15-boundary.png",
        }
    ]


def test_component_facts_have_required_schema_and_provenance():
    for page_number in (7, 8, 15, 22, 46):
        for fact in _facts(page_number):
            assert fact["component_type"] in {"pile", "beam"}
            for field in ("component_code", "fact_name", "value", "unit", "quote"):
                assert str(fact[field]).strip()
            assert fact["evidence_kind"] in {"direct", "joined"}
            assert fact["source_page"] == page_number
            assert str(fact["source_quote"]).strip()
            assert str(fact["source_table"]).strip()
            assert str(fact["join_note"]).strip()


def test_h77_page22_quantities_are_joined_and_page22_alone_is_not_identity():
    facts = {
        fact["fact_name"]: fact
        for fact in _facts(22)
        if fact["component_code"] == "H77"
    }
    for name in ("thể tích đục", "diện tích mài phẳng", "diện tích quét keo epoxy"):
        fact = facts[name]
        assert fact["evidence_kind"] == "joined"
        assert fact["identity_pages"] == [7, 22]
        assert "p7" in fact["join_note"]
        assert "Trang 22 một mình" in fact["join_note"]


def test_p46_keeps_only_lxl_and_omits_ambiguous_damage_length():
    facts = _facts(46)
    assert not any(
        fact["value"] in {"1500", "1.5"} and fact["unit"] in {"mm", "m"}
        for fact in facts
    )
    assert not any("vùng hư hỏng" in fact["fact_name"] for fact in facts)
    lxl = [fact for fact in facts if fact["fact_name"] == "chiều dài xử lý (Lxl)"]
    assert len(lxl) == 1
    assert lxl[0]["value"] == "1900"
    assert lxl[0]["unit"] == "mm"

    warnings = " ".join(_load(46)["extraction"]["warnings"])
    assert "L1 = 1500" in warnings
    assert "Lxl = L = 1900" in warnings
    ambiguous = _load(46)["evidence"]["ambiguous_lengths"]
    assert ambiguous[0]["label"] == "L (chiều dài vùng hư hỏng)"
    assert ambiguous[0]["status"] == "omitted / ambiguous"


def test_procedure_fixture_has_group_and_page_evidence():
    directory = FIXTURE_DIR.parent / "procedure_qa_2026-11-12"
    for page in (32, 33):
        item = json.loads((directory / f"report_{page:03}.json").read_text())
        facts = item["extraction"]["component_facts"]
        assert {fact["component_code"] for fact in facts} >= {"PILE-GROUP-2"}
        assert all(fact["source_page"] == page for fact in facts)
        assert all(fact["quote"] and fact["join_note"] for fact in facts)
