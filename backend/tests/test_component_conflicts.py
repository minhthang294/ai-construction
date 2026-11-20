from app.core.component_router import Preview, conflicts


def test_preview_rejects_duplicate_codes_and_mismatched_work_link():
    component = {"source_id": "one", "source_row": 5, "zone": "Test", "type": "pile",
                 "segment": 1, "design_group": None, "canonical_code": "A1", "raw_code": "A1",
                 "scope": "DESIGN_SCOPE", "drawing": "", "source": "test",
                 "verification": "NEEDS_REVIEW"}
    preview = Preview(source_sha256="a" * 64,
                      segments=[{"source_id": "S1", "zone": "Test", "number": 1}],
                      components=[component, {**component, "source_id": "two"}],
                      work_links=[{"source_id": "one", "code": "A2", "dm_row": 6, "seed_row": 5,
                                   "work": "test", "raw_location": "A2"}])
    issues = conflicts(preview)
    assert "Duplicate segment, component, source ID or work link" in issues
    assert "Work link code does not match component" in issues


def test_empty_import_is_not_a_reviewable_inventory():
    preview = Preview(source_sha256="a" * 64, segments=[], components=[], work_links=[])
    assert "Empty inventory" in conflicts(preview)


def test_zone_names_cannot_split_same_segment_by_case_or_spacing():
    component = {"source_id": "one", "source_row": 5, "zone": "Zone A", "type": "pile",
                 "segment": 1, "design_group": None, "canonical_code": "A1", "raw_code": "A1",
                 "scope": "DESIGN_SCOPE", "drawing": "", "source": "test", "verification": "NEEDS_REVIEW"}
    preview = Preview(source_sha256="a" * 64, components=[component], work_links=[],
                      segments=[{"source_id": "S1", "zone": "Zone A", "number": 1},
                                {"source_id": "S2", "zone": " zone a ", "number": 1}])
    assert "Duplicate segment, component, source ID or work link" in conflicts(preview)
