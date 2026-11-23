from app.engineering_ai.page_extraction import (
    Tile,
    merge_extractions,
    plan_page_tiles,
    validate_extraction,
)


def _component_fact(**overrides):
    fact = {
        "component_type": "pile",
        "component_code": "P-01",
        "fact_name": "chiều sâu đục",
        "value": "1",
        "unit": "cm",
        "quote": "t = 1 cm",
        "table_row": 3,
        "table_column": "t",
    }
    fact.update(overrides)
    return fact


def _valid_extraction(**overrides):
    value = {
        "page_type": "drawing",
        "title": "Bản vẽ kết cấu",
        "drawing_number": "BV-01",
        "revision": "A",
        "summary": "Trang bản vẽ kết cấu trụ.",
        "key_values": [
            {
                "name": "Chiều dày lớp bảo vệ",
                "value": "50",
                "unit": "mm",
                "quote": "lớp bảo vệ 50 mm",
            }
        ],
        "table_rows": [["Hạng mục", "Giá trị"], ["Lớp bảo vệ", "50"]],
        "warnings": ["Cần đối chiếu bản gốc."],
        "confidence": 0.8,
    }
    value.update(overrides)
    return value


def test_plan_page_tiles_covers_page_with_overlap_and_title_block():
    tiles = plan_page_tiles(1000, 800, grid=2, overlap=0.06)
    assert len(tiles) == 5
    assert all(isinstance(tile, Tile) for tile in tiles)
    assert all(
        0 <= tile.left < tile.right <= 1000
        and 0 <= tile.top < tile.bottom <= 800
        and tile.width > 0
        and tile.height > 0
        for tile in tiles
    )
    # Every page corner is covered by at least one tile.
    for x, y in ((0, 0), (999, 0), (0, 799), (999, 799)):
        assert any(
            tile.left <= x < tile.right and tile.top <= y < tile.bottom
            for tile in tiles
        )
    top_left = next(tile for tile in tiles if tile.label == "r1c1")
    top_right = next(tile for tile in tiles if tile.label == "r1c2")
    assert top_left.right > top_right.left  # horizontal overlap
    title = next(tile for tile in tiles if tile.label == "title_block")
    assert title.right == 1000 and title.bottom == 800
    assert 0 <= title.left < title.right and 0 <= title.top < title.bottom


def test_plan_page_tiles_can_disable_title_block():
    tiles = plan_page_tiles(100, 100, grid=1, include_title_block=False)
    assert len(tiles) == 1
    assert tiles[0].left == 0 and tiles[0].top == 0
    assert tiles[0].right == 100 and tiles[0].bottom == 100


def test_merge_prefers_full_page_metadata_dedupes_and_keeps_warnings():
    full = _valid_extraction(
        title="Full page title",
        summary="Full page summary",
        page_type="drawing",
        confidence=0.9,
        warnings=["Full warning"],
    )
    part_a = _valid_extraction(
        title="Tile title",
        summary="Tile summary",
        page_type="specification",
        drawing_number="BV-99",
        revision="B",
        confidence=0.7,
        warnings=["Tile warning", "Full warning"],
        key_values=[
            {
                "name": "Chiều dày lớp bảo vệ",
                "value": "50",
                "unit": "mm",
                "quote": "lớp bảo vệ 50 mm",
            },
            {
                "name": "Cường độ bê tông",
                "value": "30",
                "unit": "MPa",
                "quote": "bê tông C30",
            },
        ],
        table_rows=[["Hạng mục", "Giá trị"], ["Lớp bảo vệ", "50"]],
    )
    part_b = _valid_extraction(
        title="Another tile",
        summary="Another summary",
        confidence=0.6,
        warnings=["Second tile warning"],
        key_values=[
            {
                "name": "Cường độ bê tông",
                "value": "30",
                "unit": "MPa",
                "quote": "bê tông C30",
            }
        ],
    )
    merged = merge_extractions([part_a, part_b], full_page=full)
    assert merged["title"] == "Full page title"
    assert merged["summary"] == "Full page summary"
    assert merged["page_type"] == "drawing"
    assert merged["drawing_number"] == "BV-01"
    assert merged["revision"] == "A"
    assert len(merged["key_values"]) == 2
    assert len(merged["table_rows"]) == 2
    assert "Full warning" in merged["warnings"]
    assert "Tile warning" in merged["warnings"]
    assert "Second tile warning" in merged["warnings"]
    assert any("drawing_number" in warning for warning in merged["warnings"])
    assert any("revision" in warning for warning in merged["warnings"])
    assert not any("Mâu thuẫn title" in warning for warning in merged["warnings"])
    assert not any("Mâu thuẫn page_type" in warning for warning in merged["warnings"])
    assert 0 <= merged["confidence"] <= 1
    assert validate_extraction(merged) == []


def test_merge_filters_tile_crop_context_noise_but_keeps_full_warnings():
    full = _valid_extraction(
        warnings=["Full page: vùng crop bị che ở mép là cảnh báo cấp trang cần giữ."]
    )
    part = _valid_extraction(
        title="Tile title",
        page_type="table",
        warnings=[
            "Vùng crop không thấy số hiệu bản vẽ.",
            "Đây là vùng bị cắt, không đủ ngữ cảnh.",
            "Trong vùng không xác định được revision.",
            "Chữ mờ ở góc trái.",
            "Dấu đỏ bị che một phần.",
            "Ký hiệu thép không chắc chắn.",
        ],
    )
    merged = merge_extractions([part], full_page=full)
    warnings = merged["warnings"]
    assert any("Full page: vùng crop" in warning for warning in warnings)
    assert not any("Vùng crop không thấy" in warning for warning in warnings)
    assert not any("Đây là vùng bị cắt" in warning for warning in warnings)
    assert not any("Trong vùng" in warning for warning in warnings)
    assert any("Chữ mờ" in warning for warning in warnings)
    assert any("Dấu đỏ" in warning for warning in warnings)
    assert any("Ký hiệu thép" in warning for warning in warnings)



def test_merge_component_facts_preserves_dedupes_and_drops_invalid():
    fact = _component_fact()
    beam_fact = _component_fact(
        component_type="beam",
        component_code="B-01",
        fact_name="chiều dài sửa chữa",
        value="1900",
        unit="mm",
        quote="L = 1900 mm",
        table_row=4,
        table_column="L",
    )
    invalid = {
        "component_type": "pile",
        "fact_name": "thiếu mã",
        "value": "1",
        "unit": "cm",
        "quote": "thiếu mã",
    }
    full = _valid_extraction(component_facts=[fact])
    tile = _valid_extraction(component_facts=[dict(fact), invalid, beam_fact])

    merged = merge_extractions([tile], full_page=full)

    assert merged["component_facts"] == [fact, beam_fact]
    assert merged["key_values"] == full["key_values"]
    assert merged["table_rows"] == full["table_rows"]
    assert any(
        "component_fact" in warning and "component_code" in warning
        for warning in merged["warnings"]
    )
    assert validate_extraction(merged) == []


def test_merge_component_facts_warns_on_conflicting_values():
    full_fact = _component_fact(value="1900", unit="mm")
    tile_fact = _component_fact(value="2000", unit="mm")
    full = _valid_extraction(component_facts=[full_fact])
    tile = _valid_extraction(component_facts=[tile_fact])

    merged = merge_extractions([tile], full_page=full)

    assert merged["component_facts"] == [full_fact, tile_fact]
    assert any(
        "Mâu thuẫn component_facts" in warning
        and "1900" in warning
        and "2000" in warning
        for warning in merged["warnings"]
    )
    assert validate_extraction(merged) == []


def test_merge_component_facts_caps_at_200_and_warns():
    facts = [
        _component_fact(
            fact_name="chiều sâu đục",
            value=str(index + 1),
            table_row=index,
        )
        for index in range(201)
    ]

    merged = merge_extractions(
        [_valid_extraction(component_facts=facts)]
    )

    assert len(merged["component_facts"]) == 200
    assert any(
        "component_facts" in warning and "200" in warning
        for warning in merged["warnings"]
    )
    assert validate_extraction(merged) == []


def test_validate_extraction_rejects_bad_schema():
    assert validate_extraction(_valid_extraction()) == []
    invalid = _valid_extraction(
        page_type="unknown",
        summary="",
        confidence=1.5,
        key_values=[{"name": "x", "value": "1", "unit": "mm"}],
        table_rows=[["ok", 3]],
        warnings=["ok", 1],
    )
    errors = validate_extraction(invalid)
    assert any("page_type" in error for error in errors)
    assert any("summary" in error for error in errors)
    assert any("confidence" in error for error in errors)
    assert any("quote" in error for error in errors)
    assert any("table_rows" in error for error in errors)
    assert any("warnings" in error for error in errors)
    assert validate_extraction(None) == ["top-level JSON must be an object"]


def test_validate_extraction_accepts_legacy_schema_without_component_facts():
    value = _valid_extraction()
    assert "component_facts" not in value
    assert validate_extraction(value) == []


def test_validate_extraction_accepts_valid_pile_fact():
    value = _valid_extraction(
        component_facts=[
            {
                "component_type": "pile",
                "component_code": "P-01",
                "fact_name": "chiều sâu đục",
                "value": 1.0,
                "unit": "cm",
                "quote": "t = 1 cm",
                "group": "1",
                "segment": "2",
                "location": "cầu chính",
                "table_row": 3,
                "table_column": "t",
            }
        ]
    )
    assert validate_extraction(value) == []


def test_validate_extraction_rejects_component_fact_without_code():
    value = _valid_extraction(
        component_facts=[
            {
                "component_type": "beam",
                "fact_name": "chiều dài sửa chữa",
                "value": "1900",
                "unit": "mm",
                "quote": "L = 1900 mm",
            }
        ]
    )
    errors = validate_extraction(value)
    assert any("component_code" in error for error in errors)








