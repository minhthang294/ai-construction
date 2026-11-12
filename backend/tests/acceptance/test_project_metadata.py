"""Project setup metadata is prefilled on PYC and reused by BBNT."""
from __future__ import annotations

from app.core.models import Project
from conftest import create_record, request_payload

PROJECT_NAME = "Công trình từ thiết lập"
PROJECT_CLIENT = "Chủ đầu tư từ thiết lập"
PROJECT_LOCATION = "Địa điểm từ thiết lập"


def _seed_project(client, **overrides):
    values = {
        "id": "p1",
        "name": PROJECT_NAME,
        "client": PROJECT_CLIENT,
        "location": PROJECT_LOCATION,
    }
    values.update(overrides)
    with client.SessionLocal() as db:
        db.add(Project(**values))
        db.commit()


def _create_request(test_client, **overrides):
    response = test_client.post(
        "/api/v1/projects/p1/acceptance-requests",
        json=request_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_pyc_create_prefills_project_setup_metadata(client):
    _seed_project(client)

    created = _create_request(
        client,
        project_name=None,
        client=None,
        project_location=None,
        investor_org=None,
    )

    assert created["project_name"] == PROJECT_NAME
    assert created["client"] == PROJECT_CLIENT
    assert created["project_location"] == PROJECT_LOCATION
    # The investor/client is the same organisation in the Excel template.
    assert created["investor_org"] == PROJECT_CLIENT


def test_pyc_update_fills_blanks_without_overwriting_explicit_values(client):
    _seed_project(client)
    created = _create_request(
        client,
        project_name="Tên PYC riêng",
        client=None,
        project_location=None,
        investor_org="Đơn vị chủ đầu tư riêng",
    )
    assert created["project_name"] == "Tên PYC riêng"
    assert created["client"] == PROJECT_CLIENT
    assert created["project_location"] == PROJECT_LOCATION
    assert created["investor_org"] == "Đơn vị chủ đầu tư riêng"

    patched = client.patch(
        f"/api/v1/projects/p1/acceptance-requests/{created['id']}",
        json={"client": "", "project_location": None},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["client"] == PROJECT_CLIENT
    assert body["project_location"] == PROJECT_LOCATION
    assert body["project_name"] == "Tên PYC riêng"


def test_bbnt_snapshot_freezes_project_metadata(client):
    _seed_project(client)
    request = _create_request(
        client,
        project_name=None,
        client=None,
        project_location=None,
    )
    record = create_record(client, request["id"], participants=[])
    assert record["reused"]["project_name"] == PROJECT_NAME
    assert record["reused"]["client"] == PROJECT_CLIENT
    assert record["reused"]["project_location"] == PROJECT_LOCATION

    # Editing project setup after the BBNT was created must not alter the
    # issued record's frozen header.
    with client.SessionLocal() as db:
        project = db.get(Project, "p1")
        project.name = "Tên công trình mới"
        project.client = "Chủ đầu tư mới"
        project.location = "Địa điểm mới"
        db.commit()

    preview = client.get(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/preview"
    )
    assert preview.status_code == 200, preview.text
    cells = preview.json()["cells"]["BBNT"]
    assert cells["B1"] == f"DỰ ÁN: {PROJECT_NAME}"
    assert cells["B2"] == f"CHỦ ĐẦU TƯ: {PROJECT_CLIENT}"
    assert cells["B3"] == f"ĐỊA ĐIỂM: {PROJECT_LOCATION}"


def test_prefixed_metadata_is_not_duplicated_in_exports(client):
    request = _create_request(
        client,
        project_name="DỰ ÁN: Công trình A",
        client="CHỦ ĐẦU TƯ: Chủ đầu tư B",
        project_location="ĐỊA ĐIỂM: Vị trí C",
    )

    preview = client.get(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/preview"
    )
    assert preview.status_code == 200, preview.text
    cells = preview.json()["cells"]["PYC"]
    assert cells["C1"] == "DỰ ÁN: Công trình A"
    assert cells["C2"] == "CHỦ ĐẦU TƯ: Chủ đầu tư B"
    assert cells["C3"] == "ĐỊA ĐIỂM: Vị trí C"
