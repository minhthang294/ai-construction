from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook

from app.acceptance.dm_sync import sync_request_to_dm
from conftest import create_request


def _dm_workbook(path: Path) -> Path:
    workbook = Workbook()
    ws = workbook.active
    ws.title = "DM"
    ws["A3"] = "STT"
    ws["B3"] = "SỐ BIÊN BẢN"
    ws["C3"] = "NỘI DUNG"
    ws["D3"] = "Đối tượng"
    ws["J3"] = "Vị trí"
    ws["A6"] = 1
    ws["B6"] = 47
    ws["C6"] = "Dòng cũ"
    ws["D6"] = "Cọc A1"
    ws["E6"] = date(2026, 11, 12)
    ws["H6"] = "14h00"
    ws["J6"] = "Phân đoạn 1 - Cầu chính"
    workbook.save(path)
    return path


def _request(**overrides):
    values = {
        "number": "48",
        "content": "Đục bê tông om vỡ, tẩy gỉ cốt thép dầm",
        "subject": "dầm F-24-25, F25-27",
        "request_date": date(2026, 11, 13),
        "inspection_time": "14h45",
        "location": "Phân đoạn 1 - Cầu chính",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_sync_appends_new_pyc_and_updates_same_row(tmp_path, monkeypatch):
    workbook_path = _dm_workbook(tmp_path / "dm.xlsx")
    monkeypatch.setenv("ACCEPTANCE_DM_WORKBOOK", str(workbook_path))

    first = sync_request_to_dm(_request())
    assert first.synced is True

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    assert [ws.cell(7, column).value for column in (2, 3, 4, 8, 10)] == [
        48,
        "Đục bê tông om vỡ, tẩy gỉ cốt thép dầm",
        "dầm F-24-25, F25-27",
        "14h45",
        "Phân đoạn 1 - Cầu chính",
    ]
    assert ws.cell(7, 5).value.date() == date(2026, 11, 13)
    assert ws.cell(7, 6).value is None
    assert ws.cell(7, 7).value is None
    assert ws.cell(7, 9).value is None

    updated = sync_request_to_dm(
        _request(content="Nội dung đã sửa", inspection_time="15h00"),
        previous_number="48",
    )
    assert updated.synced is True
    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    assert ws.cell(7, 3).value == "Nội dung đã sửa"
    assert ws.cell(7, 8).value == "15h00"
    assert ws.cell(8, 2).value is None
    assert list(workbook_path.parent.glob("dm.xlsx.bak-*"))


def test_sync_updates_row_when_pyc_number_changes(tmp_path, monkeypatch):
    workbook_path = _dm_workbook(tmp_path / "dm.xlsx")
    monkeypatch.setenv("ACCEPTANCE_DM_WORKBOOK", str(workbook_path))

    assert sync_request_to_dm(_request()).synced is True
    assert sync_request_to_dm(
        _request(number="49"), previous_number="48"
    ).synced is True

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    assert ws.cell(7, 2).value == 49
    assert ws.cell(8, 2).value is None


def test_update_keeps_sampling_and_acceptance_dates_typed_by_a_human(
    tmp_path, monkeypatch
):
    workbook_path = _dm_workbook(tmp_path / "dm.xlsx")
    monkeypatch.setenv("ACCEPTANCE_DM_WORKBOOK", str(workbook_path))

    assert sync_request_to_dm(_request()).synced is True

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    ws.cell(7, 6).value = "12/11/2026"  # Lấy mẫu
    ws.cell(7, 7).value = "13/11/2026"  # NT
    ws.cell(7, 9).value = "14/11/2026"  # KẾT THÚC
    workbook.save(workbook_path)

    assert sync_request_to_dm(_request(content="Nội dung đã sửa")).synced is True

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    assert ws.cell(7, 3).value == "Nội dung đã sửa"
    assert [ws.cell(7, column).value for column in (6, 7, 9)] == [
        "12/11/2026",
        "13/11/2026",
        "14/11/2026",
    ]


def test_new_row_skips_a_blank_row_that_already_has_human_dates(
    tmp_path, monkeypatch
):
    workbook_path = _dm_workbook(tmp_path / "dm.xlsx")
    monkeypatch.setenv("ACCEPTANCE_DM_WORKBOOK", str(workbook_path))

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    ws.cell(7, 6).value = "12/11/2026"  # Lấy mẫu
    ws.cell(7, 7).value = "13/11/2026"  # NT
    ws.cell(7, 9).value = "14/11/2026"  # KẾT THÚC
    workbook.save(workbook_path)

    assert sync_request_to_dm(_request(number="48")).synced is True

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    assert [ws.cell(7, column).value for column in (6, 7, 9)] == [
        "12/11/2026",
        "13/11/2026",
        "14/11/2026",
    ]
    assert ws.cell(7, 3).value is None
    assert ws.cell(8, 2).value == 48
    assert ws.cell(8, 3).value == "Đục bê tông om vỡ, tẩy gỉ cốt thép dầm"


def test_leading_zero_number_updates_the_same_row_instead_of_duplicating(
    tmp_path, monkeypatch
):
    workbook_path = _dm_workbook(tmp_path / "dm.xlsx")
    monkeypatch.setenv("ACCEPTANCE_DM_WORKBOOK", str(workbook_path))

    assert sync_request_to_dm(_request(number="007")).synced is True
    assert sync_request_to_dm(
        _request(number="007", content="Nội dung đã sửa")
    ).synced is True

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    assert ws.cell(7, 3).value == "Nội dung đã sửa"
    assert ws.cell(8, 2).value is None
    assert ws.cell(8, 3).value is None


def test_missing_dm_workbook_returns_warning_without_raising(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "ACCEPTANCE_DM_WORKBOOK", str(tmp_path / "missing.xlsx")
    )
    result = sync_request_to_dm(_request())
    assert result.synced is False
    assert "Không tìm thấy file Excel DM" in (result.message or "")


def test_create_request_still_succeeds_when_dm_missing(
    client, tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "ACCEPTANCE_DM_WORKBOOK", str(tmp_path / "missing.xlsx")
    )
    created = create_request(client)
    assert created["number"] == "32"
    assert "Không tìm thấy file Excel DM" in (created["excel_sync_warning"] or "")


def test_create_request_writes_to_configured_dm(
    client, tmp_path, monkeypatch
):
    workbook_path = _dm_workbook(tmp_path / "dm.xlsx")
    monkeypatch.setenv("ACCEPTANCE_DM_WORKBOOK", str(workbook_path))

    created = create_request(client, number="60")
    assert created["excel_sync_warning"] is None

    workbook = load_workbook(workbook_path, data_only=False)
    ws = workbook["DM"]
    assert ws.cell(7, 2).value == 60
    assert ws.cell(7, 3).value == "Nội dung nghiệm thu thử nghiệm"
    assert ws.cell(7, 4).value == "Đối tượng nghiệm thu thử nghiệm"
    assert ws.cell(7, 5).value.date() == date(2026, 11, 11)
    assert ws.cell(7, 6).value is None
    assert ws.cell(7, 7).value is None
    assert ws.cell(7, 8).value == "15h00"
    assert ws.cell(7, 9).value is None
    assert ws.cell(7, 10).value == "Phân đoạn 1 - Cầu chính"
