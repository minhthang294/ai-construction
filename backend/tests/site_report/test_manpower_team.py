def _team_payload(**overrides):
    payload = {
        "status": "draft",
        "notes": None,
        "manpower": [],
        "manpower_team": {
            "chi_huy_truong": "Nguyễn Văn A",
            "ky_thuat": ["Trần Văn B", "Lê Thị C"],
            "lai_xe": 2,
            "bao_ve": 1,
            "cong_nhan": 10,
        },
        "work_logs": [],
        "next_day_plans": [],
    }
    payload.update(overrides)
    return payload


def _by_group(report):
    return {item["group_name"]: item for item in report["manpower"]}


def test_structured_team_roundtrip_and_zero_defaults(client):
    r = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-01",
        json=_team_payload(),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["manpower_team"] == {
        "chi_huy_truong": "Nguyễn Văn A",
        "ky_thuat": ["Lê Thị C", "Trần Văn B"],
        "lai_xe": 2,
        "bao_ve": 1,
        "cong_nhan": 10,
    }
    by_group = _by_group(data)
    assert by_group["Chỉ huy trưởng"]["person_name"] == "Nguyễn Văn A"
    assert by_group["Chỉ huy trưởng"]["count"] == 1
    engineers = [
        item for item in data["manpower"] if item["group_name"] == "Kỹ thuật"
    ]
    assert {item["person_name"] for item in engineers} == {"Trần Văn B", "Lê Thị C"}
    assert all(item["count"] == 1 for item in engineers)
    assert by_group["Lái xe"]["count"] == 2
    assert by_group["Bảo vệ"]["count"] == 1
    assert by_group["Công nhân"]["count"] == 10

    fetched = client.get("/api/v1/projects/p1/daily-reports/2026-12-01")
    assert fetched.status_code == 200
    assert fetched.json()["manpower_team"] == data["manpower_team"]

    # Only the chief/technicians are required: numeric roles default to 0 and
    # are still stored as explicit zero rows.
    defaults = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-02",
        json=_team_payload(
            manpower_team={
                "chi_huy_truong": "Nguyễn Văn A",
                "ky_thuat": [],
            }
        ),
    )
    assert defaults.status_code == 200, defaults.text
    default_data = defaults.json()
    assert default_data["manpower_team"]["lai_xe"] == 0
    assert default_data["manpower_team"]["bao_ve"] == 0
    assert default_data["manpower_team"]["cong_nhan"] == 0
    defaults_by_group = _by_group(default_data)
    assert defaults_by_group["Lái xe"]["count"] == 0
    assert defaults_by_group["Bảo vệ"]["count"] == 0
    assert defaults_by_group["Công nhân"]["count"] == 0


def test_named_people_are_saved_to_contact_directory_idempotently(client):
    first = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-03",
        json=_team_payload(),
    )
    assert first.status_code == 200, first.text

    presets = client.get("/api/v1/projects/p1/manpower-presets")
    assert presets.status_code == 200
    contacts = {
        (item["group_name"], item["person_name"]): item
        for item in presets.json()
    }
    assert set(contacts) == {
        ("Chỉ huy trưởng", "Nguyễn Văn A"),
        ("Kỹ thuật", "Trần Văn B"),
        ("Kỹ thuật", "Lê Thị C"),
    }
    assert all(item["count"] == 1 for item in contacts.values())
    # Numeric roles are not directory contacts.
    assert not any(
        item["group_name"] in {"Lái xe", "Bảo vệ", "Công nhân"}
        for item in presets.json()
    )

    # A second save with the same names must not create duplicate directory rows.
    second = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-04",
        json=_team_payload(
            manpower_team={
                "chi_huy_truong": "Nguyễn Văn A",
                "ky_thuat": ["Lê Thị C", "Trần Văn B"],
                "lai_xe": 0,
                "bao_ve": 0,
                "cong_nhan": 0,
            }
        ),
    )
    assert second.status_code == 200, second.text
    after = client.get("/api/v1/projects/p1/manpower-presets").json()
    assert len(after) == 3


def test_team_replaces_managed_rows_and_preserves_free_form_rows(client):
    legacy = {
        "group_name": "Nhà thầu phụ",
        "person_name": "Đội A",
        "count": 7,
    }
    r = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-05",
        json=_team_payload(
            manpower=[
                legacy,
                {"group_name": "Chỉ huy trưởng", "person_name": "Người cũ", "count": 9},
                {"group_name": "Kỹ thuật", "person_name": "Kỹ thuật cũ", "count": 4},
            ],
            manpower_team={
                "chi_huy_truong": "Nguyễn Văn A",
                "ky_thuat": ["Trần Văn B"],
                "lai_xe": 1,
                "bao_ve": 0,
                "cong_nhan": 3,
            },
        ),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    groups = [item["group_name"] for item in data["manpower"]]
    assert groups.count("Chỉ huy trưởng") == 1
    assert groups.count("Kỹ thuật") == 1
    assert "Nhà thầu phụ" in groups
    assert data["manpower_team"]["chi_huy_truong"] == "Nguyễn Văn A"
    assert data["manpower_team"]["ky_thuat"] == ["Trần Văn B"]


def test_legacy_manpower_rows_project_into_team_shape(client):
    r = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-06",
        json=_team_payload(
            manpower=[
                {"group_name": "Chỉ huy trưởng", "person_name": "Nguyễn Văn A", "count": 1},
                {"group_name": "Kỹ thuật", "person_name": "Trần Văn B", "count": 1},
                {"group_name": "Kỹ thuật", "person_name": "Lê Thị C", "count": 1},
                {"group_name": "Lái xe", "count": 2},
                {"group_name": "Bảo vệ", "count": None},
                {"group_name": "Công nhân", "count": 10},
                {"group_name": "Nhà thầu phụ", "count": 4},
            ],
            manpower_team=None,
        ),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["manpower_team"] == {
        "chi_huy_truong": "Nguyễn Văn A",
        "ky_thuat": ["Lê Thị C", "Trần Văn B"],
        "lai_xe": 2,
        "bao_ve": 0,
        "cong_nhan": 10,
    }
    # The old generic row is still present; only the projection is new.
    assert any(item["group_name"] == "Nhà thầu phụ" for item in data["manpower"])


def test_team_validation_and_name_cleanup(client):
    negative = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-07",
        json=_team_payload(
            manpower_team={
                "chi_huy_truong": "A",
                "ky_thuat": [],
                "lai_xe": -1,
            }
        ),
    )
    assert negative.status_code == 422

    boolean = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-07",
        json=_team_payload(
            manpower_team={
                "chi_huy_truong": "A",
                "ky_thuat": [],
                "bao_ve": True,
            }
        ),
    )
    assert boolean.status_code == 422

    cleaned = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-08",
        json=_team_payload(
            manpower_team={
                "chi_huy_truong": "   ",
                "ky_thuat": ["  Trần Văn B  ", "trần văn b", "   "],
                "lai_xe": 0,
                "bao_ve": 0,
                "cong_nhan": 0,
            }
        ),
    )
    assert cleaned.status_code == 200, cleaned.text
    team = cleaned.json()["manpower_team"]
    assert team["chi_huy_truong"] is None
    assert team["ky_thuat"] == ["Trần Văn B"]


def test_structured_team_exports_through_existing_manpower_text(client):
    saved = client.put(
        "/api/v1/projects/p1/daily-reports/2026-12-09",
        json=_team_payload(status="reviewed"),
    )
    assert saved.status_code == 200, saved.text

    exported = client.post(
        "/api/v1/projects/p1/daily-reports/2026-12-09/exports",
        json={"format": "zalo"},
    )
    assert exported.status_code == 201, exported.text
    preview = exported.json()["preview_text"]
    assert "Chỉ huy trưởng - Nguyễn Văn A: 1" in preview
    assert "Kỹ thuật - Trần Văn B: 1" in preview
    assert "Kỹ thuật - Lê Thị C: 1" in preview
    assert "Lái xe: 2" in preview
    assert "Bảo vệ: 1" in preview
    assert "Công nhân: 10" in preview
