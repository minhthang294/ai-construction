def _preset_payload(**overrides):
    payload = {
        "group_name": "Nhóm A",
        "person_name": None,
        "count": 0,
        "organization_id": "org1",
    }
    payload.update(overrides)
    return payload


def test_manpower_preset_crud_preserves_zero_vs_null(client):
    first = client.post(
        "/api/v1/projects/p1/manpower-presets", json=_preset_payload(count=0)
    )
    assert first.status_code == 201, first.text
    assert first.json()["count"] == 0

    second = client.post(
        "/api/v1/projects/p1/manpower-presets",
        json=_preset_payload(group_name="Nhóm B", person_name="Nguyễn Văn A", count=None),
    )
    assert second.status_code == 201, second.text
    assert second.json()["count"] is None

    listed = client.get("/api/v1/projects/p1/manpower-presets")
    assert listed.status_code == 200
    counts = {item["group_name"]: item["count"] for item in listed.json()}
    assert counts["Nhóm A"] == 0
    assert counts["Nhóm B"] is None

    updated = client.put(
        f"/api/v1/projects/p1/manpower-presets/{first.json()['id']}",
        json=_preset_payload(count=None, person_name="Trần Văn B"),
    )
    assert updated.status_code == 200
    assert updated.json()["count"] is None
    assert updated.json()["person_name"] == "Trần Văn B"

    deleted = client.delete(
        f"/api/v1/projects/p1/manpower-presets/{first.json()['id']}"
    )
    assert deleted.status_code == 204
    remaining = client.get("/api/v1/projects/p1/manpower-presets").json()
    assert [item["id"] for item in remaining] == [second.json()["id"]]


def test_manpower_preset_organization_must_belong_to_project(client):
    bad = client.post(
        "/api/v1/projects/p1/manpower-presets",
        json=_preset_payload(organization_id="org-other"),
    )
    assert bad.status_code == 404

    missing = client.post(
        "/api/v1/projects/p1/manpower-presets",
        json=_preset_payload(organization_id="missing-org"),
    )
    assert missing.status_code == 404


def test_manpower_preset_is_project_scoped(client):
    created = client.post(
        "/api/v1/projects/p1/manpower-presets", json=_preset_payload()
    )
    assert created.status_code == 201
    preset_id = created.json()["id"]

    assert (
        client.put(
            f"/api/v1/projects/p2/manpower-presets/{preset_id}",
            json=_preset_payload(group_name="Hijack"),
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/projects/p2/manpower-presets/{preset_id}").status_code
        == 404
    )
    assert len(client.get("/api/v1/projects/p2/manpower-presets").json()) == 0


def test_report_manpower_organization_must_belong_to_project(client):
    bad = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-11",
        json={
            "status": "draft",
            "manpower": [
                {"group_name": "A", "count": 0, "organization_id": "org-other"}
            ],
            "work_logs": [],
            "next_day_plans": [],
        },
    )
    assert bad.status_code == 404
    assert client.get("/api/v1/projects/p1/daily-reports/2026-11-11").status_code == 404

    good = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-11",
        json={
            "status": "draft",
            "manpower": [
                {"group_name": "A", "count": 0, "organization_id": "org1"},
                {"group_name": "B", "count": None, "organization_id": None},
            ],
            "work_logs": [],
            "next_day_plans": [],
        },
    )
    assert good.status_code == 200, good.text
    by_group = {item["group_name"]: item for item in good.json()["manpower"]}
    assert by_group["A"]["organization_id"] == "org1"
    assert by_group["A"]["count"] == 0
    assert by_group["B"]["count"] is None
