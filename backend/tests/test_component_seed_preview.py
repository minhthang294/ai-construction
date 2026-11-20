from pathlib import Path

from app.core.component_seed import preview_seed


def test_real_seed_preview_preserves_scope_and_links():
    path = Path(__file__).resolve().parents[2] / "Danh_muc_coc_dam_Phan_doan1_va_khung_18_phan_doan.xlsx"
    if not path.exists():
        import pytest
        pytest.skip("private seed not available")
    result = preview_seed(path.read_bytes())
    assert len(result["components"]) == 130
    assert len(result["work_links"]) == 949
    assert len({link["dm_row"] for link in result["work_links"]}) == 78
    assert len(result["segments"]) == 18
    piles = [x for x in result["components"] if x["type"] == "pile"]
    assert sum(x["design_group"] == "Nhóm 2" for x in piles) == 45
    assert sum(x["design_group"] == "Nhóm 3" for x in piles) == 39
    assert sum(x["scope"] == "ADDITIONAL_SCOPE" and x["design_group"] is None for x in result["components"]) == 34
    assert all(x["segment"] == 1 for x in result["components"])
    assert any(x["canonical_code"] == "I-40-42" for x in result["components"])
    assert any("I40-42" in str(x["raw_location"]) for x in result["work_links"])
