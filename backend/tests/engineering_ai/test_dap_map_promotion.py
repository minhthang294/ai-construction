"""Synthetic tests for scripts/promote_map_candidates.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load():
    path = ROOT / "scripts" / "promote_map_candidates.py"
    spec = importlib.util.spec_from_file_location("promote_map_candidates", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def promotion():
    return _load()


def _entry(module, entry_id, type_, canonical, zone, segment, codes):
    return module.CatalogEntry(
        id=entry_id,
        type=type_,
        canonical=canonical,
        zone=zone,
        segment=segment,
        codes=frozenset(codes),
    )


def _spec(module, markers, *, zone="Cầu chính", segment=1, exact_segment=True):
    return module.CandidateSheet(
        key="synthetic",
        sheet_id="plan",
        title="Synthetic",
        drawing="TK-00",
        page=1,
        image=Path("plan.jpg"),
        zone=zone,
        segment=segment,
        markers=markers,
        exact_segment=exact_segment,
    )


def test_keeps_only_catalog_codes_and_reports_drops(promotion):
    catalog = promotion.Catalog(
        [
            _entry(promotion, "p1", "pile", "P1", "Cầu chính", 1, {"P1"}),
        ]
    )
    sheet, stats, reviews = promotion.build_sheet(
        _spec(
            promotion,
            [
                {"code": "P1", "type": "pile", "points": [[0.5, 0.5]]},
                {"code": "X9", "type": "pile", "points": [[0.1, 0.1]]},
            ],
        ),
        catalog,
    )
    assert [marker["code"] for marker in sheet["markers"]] == ["P1"]
    assert stats["dropped"] == 1
    assert "X9" in reviews[0]["code"]
    assert "not in the project catalog" in reviews[0]["reason"]


def test_alias_resolves_to_canonical_code(promotion):
    catalog = promotion.Catalog(
        [
            _entry(promotion, "p1", "pile", "P1", "Cầu chính", 1, {"P1", "P-01"}),
        ]
    )
    sheet, stats, _ = promotion.build_sheet(
        _spec(promotion, [{"code": "P-01", "type": "pile", "points": [[0.2, 0.2]]}]),
        catalog,
    )
    assert stats["corrected"] == 0
    assert sheet["markers"][0]["code"] == "P1"


def test_unique_catalog_segment_corrects_candidate_segment(promotion):
    catalog = promotion.Catalog(
        [
            _entry(promotion, "b1", "beam", "B1", "Cầu dẫn", 3, {"B1"}),
        ]
    )
    sheet, stats, reviews = promotion.build_sheet(
        _spec(
            promotion,
            [{"code": "B1", "type": "beam", "points": [[0.1, 0.1], [0.2, 0.2]]}],
            zone="Cầu dẫn",
            segment=2,
            exact_segment=False,
        ),
        catalog,
    )
    assert sheet["markers"][0]["segment"] == 3
    assert sheet["segment"] == 3
    assert stats["corrected"] == 1
    assert "Cầu dẫn 3" in reviews[0]["reason"]


def test_exact_segment_drops_cross_segment_match(promotion):
    catalog = promotion.Catalog(
        [
            _entry(promotion, "b1", "beam", "B1", "Cầu chính", 2, {"B1"}),
        ]
    )
    sheet, stats, _ = promotion.build_sheet(
        _spec(
            promotion,
            [{"code": "B1", "type": "beam", "points": [[0.1, 0.1], [0.2, 0.2]]}],
            zone="Bunke",
            segment=1,
            exact_segment=True,
        ),
        catalog,
    )
    assert sheet["markers"] == []
    assert stats["dropped"] == 1


def test_mixed_bunke_sheet_uses_pd2_piles_and_bunke_beams(promotion):
    catalog = promotion.Catalog(
        [
            _entry(promotion, "p1", "pile", "A153", "Cầu chính", 2, {"A153"}),
            _entry(promotion, "b1", "beam", "A-B-153", "Bunke", 1, {"A-B-153"}),
        ]
    )
    sheet, stats, _ = promotion.build_sheet(
        _spec(
            promotion,
            [
                {
                    "code": "A153",
                    "type": "pile",
                    "points": [[0.3, 0.6]],
                    "zone": "Cầu chính",
                    "segment": 2,
                },
                {
                    "code": "A-B-153",
                    "type": "beam",
                    "points": [[0.3, 0.6], [0.3, 0.4]],
                    "zone": "Bunke",
                    "segment": 1,
                },
            ],
            zone="Bunke",
            segment=1,
            exact_segment=True,
        ),
        catalog,
    )
    assert stats["promoted"] == 2
    assert stats["dropped"] == 0
    assert sheet["zone"] is None
    assert sheet["segment"] is None
    assert {(m["code"], m["zone"], m["segment"]) for m in sheet["markers"]} == {
        ("A153", "Cầu chính", 2),
        ("A-B-153", "Bunke", 1),
    }


def test_beam_with_one_point_and_corner_are_dropped(promotion):
    catalog = promotion.Catalog(
        [
            _entry(promotion, "b1", "beam", "B1", "Cầu dẫn", 2, {"B1"}),
        ]
    )
    sheet, stats, _ = promotion.build_sheet(
        _spec(
            promotion,
            [
                {"code": "B1", "type": "beam", "points": [[0.1, 0.1]]},
                {"code": "Q-1", "type": "corner_beam", "points": [[0.1, 0.1]]},
            ],
            zone="Cầu dẫn",
            segment=2,
            exact_segment=False,
        ),
        catalog,
    )
    assert sheet["markers"] == []
    assert stats["dropped"] == 2


def test_sheet_id_is_stable_and_schema_safe(promotion):
    assert promotion._sheet_id("pd02-plan", 2) == "plan"
    assert promotion._sheet_id("pd02-o-q-186-plan-label", 2) == "o-q-186"
    assert promotion._sheet_id("PD03-plan", 3) == "plan"
