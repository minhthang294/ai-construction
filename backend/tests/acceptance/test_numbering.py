"""Deterministic numbering configuration and atomic allocation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.acceptance.models import Base
from app.acceptance.schemas import NumberingIn, RequestIn
from app.acceptance.service import create_request, update_numbering
from conftest import create_record, create_request as api_create_request


def _configure(client, kind, **overrides):
    payload = {
        "prefix": "PYC-" if kind == "pyc" else "BBNT-",
        "start_number": 1,
        "width": 3,
        "reset_policy": "never",
        "date_format": "%Y",
    }
    payload.update(overrides)
    response = client.put(
        f"/api/v1/projects/p1/acceptance-numbering/{kind}",
        json=payload,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_numbering_configuration_and_pyc_auto_numbers(client):
    configured = _configure(client, "pyc", prefix="P-", width=3)
    assert configured["prefix"] == "P-"
    assert configured["next_number"] == 1

    first = api_create_request(client, number=None)
    second = api_create_request(client, number=None)
    assert first["number"] == "P-001"
    assert second["number"] == "P-002"

    listed = client.get("/api/v1/projects/p1/acceptance-numbering")
    assert listed.status_code == 200
    assert {item["kind"] for item in listed.json()} == {"pyc", "bbnt"}


def test_monthly_reset_policy_uses_period_key_and_date_format(client):
    now = datetime.now(timezone.utc)
    configured = _configure(
        client,
        "pyc",
        prefix="M-",
        start_number=1,
        width=2,
        reset_policy="monthly",
        date_format="%Y%m",
    )
    assert configured["period_key"] == now.strftime("%Y-%m")
    request = api_create_request(client, number=None)
    assert request["number"] == f"M-{now.strftime('%Y%m')}01"


def test_bbnt_uses_configured_sequence_or_defaults_to_pyc_number(client):
    plain_request = api_create_request(client, number="77")
    plain_record = create_record(client, plain_request["id"])
    assert plain_record["number"] == "77"

    _configure(client, "bbnt", prefix="B-", width=2)
    request = api_create_request(client, number=None)
    record = create_record(client, request["id"])
    assert record["number"] == "B-01"

    request2 = api_create_request(client, number=None)
    record2 = create_record(client, request2["id"])
    assert record2["number"] == "B-02"


def test_concurrent_requests_get_unique_contiguous_numbers(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'numbering.db'}",
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as db:
        update_numbering(
            db,
            "p1",
            "pyc",
            NumberingIn(prefix="P-", start_number=1, width=4, reset_policy="never"),
        )

    workers = 12
    barrier = threading.Barrier(workers)

    def create_one(index: int) -> str:
        barrier.wait(timeout=10)
        with SessionLocal() as db:
            request = create_request(
                db,
                "p1",
                RequestIn(project_name=f"Project {index}", location=f"Line {index}"),
                f"user-{index}",
            )
            return request.number

    with ThreadPoolExecutor(max_workers=workers) as pool:
        numbers = list(pool.map(create_one, range(workers)))

    assert len(set(numbers)) == workers
    assert sorted(numbers) == [f"P-{value:04d}" for value in range(1, workers + 1)]
