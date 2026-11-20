"""Deterministically mirror saved PYCs into the project's DM workbook.

This is intentionally not an AI feature.  The database remains the source of
truth; the workbook is a convenience copy for the site team.  A locked,
missing, or malformed workbook must never prevent the PYC from being saved.
"""

from __future__ import annotations

import copy
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from openpyxl import load_workbook

LOGGER = logging.getLogger(__name__)
WORKBOOK_ENV = "ACCEPTANCE_DM_WORKBOOK"
DM_SHEET = "DM"
FIRST_DATA_ROW = 6


@dataclass(frozen=True)
class DMSyncResult:
    synced: bool
    message: Optional[str] = None
    path: Optional[Path] = None


def configured_workbook() -> Optional[Path]:
    raw = os.getenv(WORKBOOK_ENV, "").strip()
    return Path(raw).expanduser() if raw else None


def _number_value(number: str) -> Any:
    value = (number or "").strip()
    return int(value) if value.isdigit() else value


def _number_key(value: Any) -> Optional[str]:
    """Normalise a number so 1, 1.0 and "001" compare equal."""

    if value is None:
        return None
    if isinstance(value, str) and value.startswith("="):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if not text:
        return None
    return (text.lstrip("0") or "0") if text.isdigit() else text


def _same_number(value: Any, number: str) -> bool:
    key = _number_key(value)
    return key is not None and key == _number_key(number)


def _last_data_row(ws) -> int:
    last = FIRST_DATA_ROW - 1
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        content = ws.cell(row, 3).value
        subject = ws.cell(row, 4).value
        number = ws.cell(row, 2).value
        is_number = number not in (None, "") and not (
            isinstance(number, str) and number.startswith("=")
        )
        if content not in (None, "") or subject not in (None, "") or is_number:
            last = row
    return last


def _find_row(ws, number: str, previous_number: Optional[str]) -> Optional[int]:
    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        if _same_number(ws.cell(row, 2).value, number):
            return row
    if previous_number and previous_number != number:
        for row in range(FIRST_DATA_ROW, ws.max_row + 1):
            if _same_number(ws.cell(row, 2).value, previous_number):
                return row
    return None


def _next_empty_row(ws) -> int:
    candidate = max(FIRST_DATA_ROW, _last_data_row(ws) + 1)
    while candidate <= ws.max_row:
        if (
            ws.cell(candidate, 3).value in (None, "")
            and ws.cell(candidate, 4).value in (None, "")
            and not (
                isinstance(ws.cell(candidate, 2).value, (int, float))
            )
            # E-J are human fields too; never reuse a row that already holds one.
            and all(
                ws.cell(candidate, column).value in (None, "")
                for column in range(5, 11)
            )
        ):
            return candidate
        candidate += 1
    return candidate


def _copy_row_style(ws, source_row: int, target_row: int) -> None:
    for column in range(1, 11):
        source = ws.cell(source_row, column)
        target = ws.cell(target_row, column)
        target._style = copy.copy(source._style)
        target.number_format = source.number_format
        target.font = copy.copy(source.font)
        target.border = copy.copy(source.border)
        target.fill = copy.copy(source.fill)
        target.alignment = copy.copy(source.alignment)
        target.protection = copy.copy(source.protection)


def _write_request(ws, request: Any, previous_number: Optional[str]) -> int:
    number = str(request.number or "").strip()
    if not number:
        raise ValueError("PYC number is empty")
    row = _find_row(ws, number, previous_number)
    new_row = row is None
    if row is None:
        row = _next_empty_row(ws)
        if row == FIRST_DATA_ROW:
            row = FIRST_DATA_ROW
        _copy_row_style(ws, max(FIRST_DATA_ROW, row - 1), row)
    if ws.cell(row, 1).value in (None, ""):
        ws.cell(row, 1).value = f"=A{max(FIRST_DATA_ROW, row - 1)}+1"

    ws.cell(row, 2).value = _number_value(number)
    ws.cell(row, 3).value = request.content
    ws.cell(row, 4).value = request.subject
    request_date = request.request_date
    if isinstance(request_date, datetime):
        request_date = request_date.date()
    if isinstance(request_date, date):
        ws.cell(row, 5).value = request_date
    elif request_date:
        ws.cell(row, 5).value = str(request_date)
    else:
        ws.cell(row, 5).value = None
    # Lấy mẫu / NT / Kết thúc stay blank unless the PYC model gains those fields.
    # Only a row this app creates is cleared: on an existing row a human may have
    # typed those dates, and an update must not wipe them.
    if new_row:
        ws.cell(row, 6).value = None
        ws.cell(row, 7).value = None
        ws.cell(row, 9).value = None
    ws.cell(row, 8).value = request.inspection_time
    ws.cell(row, 10).value = request.location
    if new_row:
        ws.row_dimensions[row].height = 60
    return row


def _backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    return backup


def sync_request_to_dm(
    request: Any, *, previous_number: Optional[str] = None
) -> DMSyncResult:
    """Append/update one PYC row.  Never raise into the request transaction."""

    path = configured_workbook()
    if path is None:
        return DMSyncResult(False, None, None)
    if not path.is_file():
        return DMSyncResult(
            False,
            f"Không tìm thấy file Excel DM ({path}); PYC vẫn được lưu.",
            path,
        )

    lock_handle = None
    try:
        lock_path = path.with_name(f"{path.name}.lock")
        lock_handle = lock_path.open("a+")
        try:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:  # pragma: no cover - Windows fallback
            pass
        except BlockingIOError:
            return DMSyncResult(
                False,
                "File Excel DM đang được ghi bởi tiến trình khác; PYC vẫn được lưu.",
                path,
            )

        workbook = load_workbook(path, data_only=False, keep_links=True)
        if DM_SHEET not in workbook.sheetnames:
            return DMSyncResult(
                False,
                "File Excel DM không có sheet DM; PYC vẫn được lưu.",
                path,
            )
        worksheet = workbook[DM_SHEET]
        row = _write_request(worksheet, request, previous_number)
        _backup(path)
        temp = path.with_name(f".{path.stem}.tmp-{os.getpid()}.xlsx")
        workbook.calculation.fullCalcOnLoad = True
        try:
            workbook.save(temp)
            os.replace(temp, path)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
        LOGGER.info("Synced acceptance request %s to DM row %s", request.number, row)
        return DMSyncResult(True, "Đã ghi vào file Excel DM.", path)
    except Exception as exc:  # noqa: BLE001 - Excel must never block PYC save
        LOGGER.exception("Could not sync acceptance request %s to DM", request.number)
        return DMSyncResult(
            False,
            f"Không ghi được file Excel DM ({type(exc).__name__}); PYC vẫn được lưu.",
            path,
        )
    finally:
        if lock_handle is not None:
            try:
                import fcntl

                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            lock_handle.close()
