"""Synthetic tests for the segment-batch helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load():
    path = ROOT / "scripts" / "create_segment_batches.py"
    spec = importlib.util.spec_from_file_location("create_segment_batches", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def batches():
    return _load()


def _component(module, code, zone, segment, type_="pile", component_id=None):
    return {
        "id": component_id or f"id-{code}",
        "code": code,
        "type": type_,
        "zone": zone,
        "segment": segment,
    }


def test_live_segments_and_bunke_drawings(batches):
    manifests = [
        (
            "cau-chinh-pd1",
            {"sheets": [{"zone": "Cầu chính", "segment": 1, "drawing": "TK-31",
                         "markers": [{"code": "I1", "zone": "Cầu chính", "segment": 1}]}]},
        ),
        (
            "pd2",
            {"sheets": [{"zone": None, "segment": None, "drawing": "TK-32",
                         "markers": [{"code": "F1", "zone": "Cầu chính", "segment": 2}]}]},
        ),
        (
            "bunke",
            {"sheets": [{"zone": None, "segment": None, "drawing": "TK-32",
                         "markers": [{"code": "A153", "zone": "Cầu chính", "segment": 2},
                                     {"code": "A-B-153", "zone": "Bunke", "segment": 1}]}]},
        ),
        (
            "cau-dan-pd02",
            {"sheets": [{"zone": "Cầu dẫn", "segment": 2, "drawing": "TK-88",
                         "markers": [{"code": "O-Q-1", "zone": "Cầu dẫn", "segment": 2}]}]},
        ),
    ]
    assert batches.live_cau_chinh_segments(manifests) == {
        1: {"cau-chinh-pd1"},
        2: {"pd2", "bunke"},
    }


def test_segment_components_excludes_bunke_and_other_segments(batches):
    components = [
        _component(batches, "P1", "Cầu chính", 1),
        _component(batches, "P2", "Cầu chính", 2),
        _component(batches, "A153", "Cầu chính", 2),
        _component(batches, "A-B-153", "Bunke", 1, "beam"),
        _component(batches, "M1", "Cầu dẫn", 1),
    ]
    assert [item["code"] for item in batches.segment_components(components, 1)] == ["P1"]
    assert [item["code"] for item in batches.segment_components(components, 2)] == [
        "P2", "A153",
    ]


def test_bunke_membership_checks_existing_pd2_batch(batches):
    components = [
        _component(batches, code, "Cầu chính", 2)
        for code in batches.BUNKE_PILE_CODES
    ]
    components += [
        _component(batches, code, "Bunke", 1, "beam")
        for code in batches.BUNKE_BEAM_CODES
    ]
    batch_ids = {item["id"] for item in components}
    status = batches.bunke_membership(components, batch_ids)
    assert status["piles_present"] == 17
    assert status["missing_piles"] == []
    assert status["beams_present"] == 2
    assert status["missing_beams"] == []

    removed = components[0]["id"]
    status = batches.bunke_membership(components, batch_ids - {removed})
    assert status["missing_piles"] == [batches.BUNKE_PILE_CODES[0]]


def test_bunke_membership_does_not_treat_bunke_copies_as_sources(batches):
    components = [
        _component(batches, code, "Bunke", 1)
        for code in batches.BUNKE_PILE_CODES
    ]
    status = batches.bunke_membership(components, {item["id"] for item in components})
    assert status["piles_present"] == 0
    assert status["missing_piles"] == list(batches.BUNKE_PILE_CODES)


def test_batch_name(batches):
    assert batches.batch_name(1) == "PD1 Cầu chính"
    assert batches.batch_name(3) == "PD3 Cầu chính"
