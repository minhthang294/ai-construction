from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.models import AuditLog


def _payload(**overrides):
    payload = {
        "status": "draft",
        "notes": "test",
        "manpower": [
            {"group_name": "Workers", "count": 0},
            {"group_name": "Engineers", "count": None},
            {"group_name": "Supervisors", "count": 5},
        ],
        "work_logs": [],
        "next_day_plans": [],
    }
    payload.update(overrides)
    return payload


def test_zero_vs_null_manpower_preserved(client):
    r = client.put("/api/v1/projects/p1/daily-reports/2026-11-11", json=_payload())
    assert r.status_code == 200, r.text
    data = r.json()
    by_group = {m["group_name"]: m["count"] for m in data["manpower"]}
    assert by_group["Workers"] == 0
    assert by_group["Engineers"] is None
    assert by_group["Supervisors"] == 5

    # GET roundtrip must keep the distinction, not coerce 0 to null.
    r2 = client.get("/api/v1/projects/p1/daily-reports/2026-11-11")
    assert r2.status_code == 200
    by_group2 = {m["group_name"]: m["count"] for m in r2.json()["manpower"]}
    assert by_group2["Workers"] == 0
    assert by_group2["Engineers"] is None
    assert by_group2["Supervisors"] == 5


def test_upsert_idempotent(client):
    payload = {"manpower": [{"group_name": "A", "count": 1}], "work_logs": [], "next_day_plans": []}
    r1 = client.put("/api/v1/projects/p1/daily-reports/2026-11-12", json=payload)
    assert r1.status_code == 200
    r2 = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-12",
        json={"manpower": [{"group_name": "A", "count": 2}], "work_logs": [], "next_day_plans": []},
    )
    assert r2.status_code == 200
    r3 = client.get("/api/v1/projects/p1/daily-reports/2026-11-12")
    assert len(r3.json()["manpower"]) == 1
    assert r3.json()["manpower"][0]["count"] == 2


def test_report_not_found(client):
    r = client.get("/api/v1/projects/p1/daily-reports/2020-01-01")
    assert r.status_code == 404


def test_invalid_status_and_negative_count_rejected(client):
    bad_status = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-13",
        json=_payload(status="approved"),
    )
    assert bad_status.status_code == 422

    negative = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-13",
        json=_payload(manpower=[{"group_name": "A", "count": -1}]),
    )
    assert negative.status_code == 422

    blank = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-13",
        json=_payload(manpower=[{"group_name": "   ", "count": 1}]),
    )
    assert blank.status_code == 422

    boolean = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-13",
        json=_payload(manpower=[{"group_name": "A", "count": False}]),
    )
    assert boolean.status_code == 422
    # No report was created by an invalid request.
    assert client.get("/api/v1/projects/p1/daily-reports/2026-11-13").status_code == 404


def test_work_log_time_order_and_local_time_normalisation(client):
    bad = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-14",
        json=_payload(
            work_logs=[
                {
                    "start_time": "2026-11-14T10:00:00+07:00",
                    "end_time": "2026-11-14T09:00:00+07:00",
                }
            ]
        ),
    )
    assert bad.status_code == 422

    good = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-14",
        json=_payload(
            work_logs=[
                {
                    "start_time": "2026-11-14T09:00:00",  # naive = Asia/Ho_Chi_Minh
                    "end_time": "2026-11-14T10:00:00",
                }
            ]
        ),
    )
    assert good.status_code == 200
    work_log = good.json()["work_logs"][0]
    start = datetime.fromisoformat(work_log["start_time"].replace("Z", "+00:00"))
    assert start.utcoffset().total_seconds() == 0
    assert start.hour == 2  # 09:00 +07:00 == 02:00 UTC


def test_work_item_must_belong_to_project(client):
    cross_project = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-15",
        json=_payload(work_logs=[{"work_item_id": "w-other", "location": "X"}]),
    )
    assert cross_project.status_code == 404
    assert client.get("/api/v1/projects/p1/daily-reports/2026-11-15").status_code == 404

    unknown = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-15",
        json=_payload(next_day_plans=[{"plan_date": "2026-11-16", "work_item_id": "missing"}]),
    )
    assert unknown.status_code == 404

    valid = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-15",
        json=_payload(
            work_logs=[{"work_item_id": "w1", "location": "X"}],
            next_day_plans=[{"plan_date": "2026-11-16", "work_item_id": "w1"}],
        ),
    )
    assert valid.status_code == 200
    assert valid.json()["work_logs"][0]["work_item_id"] == "w1"
    assert valid.json()["next_day_plans"][0]["work_item_id"] == "w1"


def test_invalid_work_item_does_not_destroy_previous_draft(client):
    first = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-17",
        json=_payload(manpower=[{"group_name": "Keep", "count": 3}]),
    )
    assert first.status_code == 200

    invalid = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-17",
        json=_payload(
            manpower=[],
            work_logs=[{"work_item_id": "w-other"}],
        ),
    )
    assert invalid.status_code == 404

    after = client.get("/api/v1/projects/p1/daily-reports/2026-11-17")
    assert after.status_code == 200
    assert [m["group_name"] for m in after.json()["manpower"]] == ["Keep"]


def test_structured_site_notes_roundtrip(client):
    payload = _payload(
        site_notes={
            "weather": "  Nắng nhẹ  ",
            "materials": "Thép D16",
            "equipment": "",
            "incidents": None,
            "difficulties": "Mưa chiều",
            "safety": "Đủ PPE",
            "recommendations": "Bổ sung đèn",
            "other": "Không",
        }
    )
    r = client.put("/api/v1/projects/p1/daily-reports/2026-11-20", json=payload)
    assert r.status_code == 200, r.text
    notes = r.json()["site_notes"]
    assert notes["weather"] == "Nắng nhẹ"
    assert notes["materials"] == "Thép D16"
    assert notes["equipment"] is None
    assert notes["incidents"] is None
    assert notes["safety"] == "Đủ PPE"

    fetched = client.get("/api/v1/projects/p1/daily-reports/2026-11-20").json()
    assert fetched["site_notes"]["weather"] == "Nắng nhẹ"
    assert fetched["site_notes"]["equipment"] is None

    # Omitting site_notes stores an empty structured object, not fabricated text.
    other = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-21",
        json=_payload(),
    )
    assert other.status_code == 200
    assert all(value is None for value in other.json()["site_notes"].values())


def test_reviewed_status_roundtrip(client):
    r = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-18",
        json=_payload(status="reviewed"),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "reviewed"
    assert client.get("/api/v1/projects/p1/daily-reports/2026-11-18").json()["status"] == "reviewed"


def test_audit_log_written_for_report_upsert(client, db_engine):
    r = client.put(
        "/api/v1/projects/p1/daily-reports/2026-11-19",
        json=_payload(status="reviewed"),
    )
    assert r.status_code == 200
    Session = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        rows = db.execute(
            select(AuditLog).where(
                AuditLog.project_id == "p1",
                AuditLog.action == "upsert_daily_report",
            )
        ).scalars().all()
    assert rows
    assert rows[-1].actor_id == "test-user"
    assert rows[-1].entity == "DailyReport"
