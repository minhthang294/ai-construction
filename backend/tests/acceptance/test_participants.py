"""Participant library CRUD and PYC/BBNT snapshot behavior."""
from __future__ import annotations

from conftest import create_record, create_request, record_payload


def _profile(client, **overrides):
    payload = {
        "full_name": "Nguyễn Văn A",
        "organization": "Công ty A",
        "position": "Chỉ huy trưởng",
        "role": "requester",
        "active": True,
    }
    payload.update(overrides)
    response = client.post("/api/v1/projects/p1/acceptance-participants", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_participant_library_crud(client):
    profile = _profile(client)
    listed = client.get("/api/v1/projects/p1/acceptance-participants")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [profile["id"]]

    fetched = client.get(f"/api/v1/projects/p1/acceptance-participants/{profile['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["full_name"] == "Nguyễn Văn A"

    patched = client.patch(
        f"/api/v1/projects/p1/acceptance-participants/{profile['id']}",
        json={"position": "Giám đốc", "active": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["position"] == "Giám đốc"
    assert patched.json()["active"] is False

    active_only = client.get("/api/v1/projects/p1/acceptance-participants?active_only=true")
    assert active_only.json() == []

    deleted = client.delete(f"/api/v1/projects/p1/acceptance-participants/{profile['id']}")
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/projects/p1/acceptance-participants/{profile['id']}"
    ).status_code == 404


def test_pyc_profile_selection_saves_snapshot_names(client):
    requester = _profile(client, full_name="Trần Văn Thi công", organization="Nhà thầu")
    supervisor = _profile(
        client,
        full_name="Lê Văn Giám sát",
        organization="TVGS",
        position="TVGS",
        role="supervisor",
    )
    investor = _profile(
        client,
        full_name="Phạm Văn Chủ đầu tư",
        organization="CĐT",
        position="Giám đốc",
        role="investor",
    )

    request = create_request(
        client,
        requested_by_profile_id=requester["id"],
        supervisor_profile_id=supervisor["id"],
        investor_profile_id=investor["id"],
    )
    assert request["requested_by_profile_id"] == requester["id"]
    assert request["requested_by_name"] == "Trần Văn Thi công"
    assert request["supervisor_name"] == "Lê Văn Giám sát"
    assert request["investor_name"] == "Phạm Văn Chủ đầu tư"
    assert request["contractor_org"] == "Nhà thầu"
    assert request["supervisor_org"] == "TVGS"
    assert request["investor_org"] == "CĐT"


def test_bbnt_prefills_participants_from_selected_pyc_profiles(client):
    requester = _profile(client, full_name="Trần Văn Thi công", organization="Nhà thầu")
    supervisor = _profile(
        client,
        full_name="Lê Văn Giám sát",
        organization="TVGS",
        role="supervisor",
    )
    investor = _profile(
        client,
        full_name="Phạm Văn Chủ đầu tư",
        organization="CĐT",
        role="investor",
    )
    request = create_request(
        client,
        requested_by_profile_id=requester["id"],
        supervisor_profile_id=supervisor["id"],
        investor_profile_id=investor["id"],
    )
    payload = record_payload(request["id"])
    payload.pop("participants")
    payload.pop("checklist")
    response = client.post("/api/v1/projects/p1/acceptance-records", json=payload)
    assert response.status_code == 201, response.text
    participants = response.json()["participants"]
    assert {item["person_name"] for item in participants} == {
        "Trần Văn Thi công",
        "Lê Văn Giám sát",
        "Phạm Văn Chủ đầu tư",
    }
    assert response.json()["result"] is None
    assert {item["state"] for item in response.json()["checklist"]} == {"unconfirmed"}


def test_profile_must_be_active_and_in_project(client):
    inactive = _profile(client, full_name="Người nghỉ", active=False)
    rejected = client.post(
        "/api/v1/projects/p1/acceptance-requests",
        json={"number": "P-1", "requested_by_profile_id": inactive["id"]},
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "participant_profile_inactive"

    other = _profile(client, full_name="Người công trình khác")
    foreign = client.post(
        "/api/v1/projects/p2/acceptance-requests",
        json={"number": "P-2", "requested_by_profile_id": other["id"]},
    )
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "participant_profile_not_found"
