"""Shared fixtures for the Acceptance module tests."""

from __future__ import annotations

import os
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ACCEPTANCE_STORAGE", "/tmp/opencode/acceptance-test-storage")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.acceptance.dependencies import (
    require_confirmer,
    require_editor,
    require_project_member,
)
from app.acceptance.models import Base
from app.acceptance.router import get_db, router
from app.core.models import WorkItem
from app.engineering_ai.models import DocumentPage, SourceDocument
from app.site.models import DailyReport, SitePhoto

# Canonical, repo-owned template.  Tests never read the user's working copy in
# Downloads: it may be open in LibreOffice, saved with a different hash, or
# missing xl/calcChain.xml at any moment.
CANONICAL_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "templates"
    / "acceptance-original.xlsx"
)


def _make_synthetic_template(path: Path) -> Path:
    """Portable template with the same PYC/BBNT anchors and old defaults."""

    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from PIL import Image

    wb = Workbook()
    wb.remove(wb.active)
    dm = wb.create_sheet("DM")
    pyc = wb.create_sheet("PYC")
    bbnt = wb.create_sheet("BBNT")
    pyc2 = wb.create_sheet("PYC (2)")
    pyc2.sheet_state = "hidden"
    bblm = wb.create_sheet("BB LM bt")
    bblm.sheet_state = "hidden"
    foxz = wb.create_sheet("foxz")
    foxz.sheet_state = "veryHidden"

    thin = Side(style="thin")
    medium = Side(style="medium")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    font = Font(name="Times New Roman", size=13)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    fill = PatternFill("solid", fgColor="FFFFFF")

    def touch(ws, cells):
        for coord in cells:
            cell = ws[coord]
            cell.font = font
            cell.border = border
            cell.alignment = center
            cell.fill = fill

    pyc_cells = (
        "C1 C2 C3 B6 F6 B7 B10 D10 E10 H10 I10 K10 D14 D15 D16 A20 E20 H20"
    ).split()
    bbnt_cells = (
        "B1 B2 B3 B5 D5 B6 A8 A11 A14 B9 D9 B10 D10 B12 D12 B13 D13 B15 D15 B16 D16 "
        "B18 B19 D18 D19 D24 E24 D25 E25 D26 E26 D27 E27 D28 E28 D29 E29 D30 E30 "
        "A32 A33 A34 A36 A37 A43"
    ).split()
    touch(pyc, pyc_cells)
    touch(bbnt, bbnt_cells)
    touch(pyc2, pyc_cells)

    pyc.merge_cells("C1:I1")
    pyc.merge_cells("C2:I2")
    pyc.merge_cells("C3:I3")
    pyc.merge_cells("F6:K6")
    pyc.merge_cells("B10:C13")
    pyc.merge_cells("D10:D13")
    pyc.merge_cells("E10:G13")
    pyc.merge_cells("H10:H13")
    pyc.merge_cells("I10:J13")
    pyc.merge_cells("K10:K13")
    pyc.merge_cells("A14:A16")
    pyc.merge_cells("B14:C14")
    pyc.merge_cells("B15:C15")
    pyc.merge_cells("B16:C16")
    pyc.merge_cells("A17:D17")
    pyc.merge_cells("E17:K17")
    pyc.merge_cells("A18:D18")
    pyc.merge_cells("E18:G18")
    pyc.merge_cells("H18:K18")
    pyc.merge_cells("A19:D19")
    pyc.merge_cells("E19:G19")
    pyc.merge_cells("H19:K19")
    pyc.merge_cells("A20:D20")
    pyc.merge_cells("E20:G20")
    pyc.merge_cells("H20:K20")
    pyc.print_area = "A1:K21"

    bbnt.merge_cells("B1:E1")
    bbnt.merge_cells("B2:E2")
    bbnt.merge_cells("B3:E3")
    bbnt.merge_cells("D5:F5")
    bbnt.merge_cells("D9:F9")
    bbnt.merge_cells("D10:F10")
    bbnt.merge_cells("D12:F12")
    bbnt.merge_cells("D13:F13")
    bbnt.merge_cells("D15:F15")
    bbnt.merge_cells("D16:F16")
    bbnt.merge_cells("A32:F32")
    bbnt.merge_cells("A33:F33")
    bbnt.merge_cells("A34:F34")
    bbnt.merge_cells("A36:F36")
    bbnt.merge_cells("A37:F37")
    bbnt.merge_cells("A43:F43")
    bbnt.print_area = "A1:F43"

    pyc["C1"] = "DỰ ÁN: OLD PROJECT"
    pyc["C2"] = "CHỦ ĐẦU TƯ: OLD CLIENT"
    pyc["C3"] = "ĐỊA ĐIỂM: OLD LOCATION"
    pyc["A6"] = "Số: YC-"
    pyc["B6"] = 32
    pyc["A7"] = "Vị trí: "
    pyc["B7"] = "OLD POSITION"
    pyc["A8"] = "STT"
    pyc["B8"] = "Thời gian nghiệm thu"
    pyc["E8"] = "Nội dung nghiệm thu"
    pyc["H8"] = "Lĩnh vực nghiệm thu"
    pyc["B9"] = "Ngày"
    pyc["D9"] = "Giờ"
    pyc["H9"] = "Xây dựng"
    pyc["I9"] = "Điện"
    pyc["K9"] = "Cơ"
    pyc["B10"] = "2026-10-13"
    pyc["D10"] = "21h00"
    pyc["E10"] = "OLD CONTENT"
    pyc["H10"] = "☑"
    pyc["A14"] = "Mức độ yêu cầu"
    pyc["B14"] = "Bình thường"
    pyc["D14"] = "☑"
    pyc["B15"] = "Gấp"
    pyc["D15"] = "□"
    pyc["B16"] = "Rất gấp"
    pyc["D16"] = "□"
    pyc["A18"] = "NHÀ THẦU YÊU CẦU"
    pyc["E18"] = "Tư vấn giám sát"
    pyc["H18"] = "Chủ đầu tư"
    pyc["A20"] = "OLD CONTRACTOR"
    pyc["E20"] = "OLD SUPERVISOR"
    pyc["H20"] = "OLD INVESTOR"

    pyc2["B6"] = 99
    pyc2["A20"] = "OLD HIDDEN CONTRACTOR"
    pyc2["E20"] = "OLD HIDDEN SUPERVISOR"
    pyc2["H20"] = "OLD HIDDEN INVESTOR"

    bbnt["B1"] = "DỰ ÁN: OLD PROJECT"
    bbnt["B2"] = "CHỦ ĐẦU TƯ: OLD CLIENT"
    bbnt["B3"] = "ĐỊA ĐIỂM: OLD LOCATION"
    bbnt["A5"] = "Số: NT-"
    bbnt["B5"] = 32
    bbnt["D5"] = "2026-10-13"
    bbnt["B6"] = "OLD POSITION"
    bbnt["A8"] = "Đại diện Chủ đầu tư: OLD INVESTOR ORG"
    bbnt["A9"] = "Ông/Bà: "
    bbnt["C9"] = "Chức vụ:"
    bbnt["A10"] = "Ông/Bà: "
    bbnt["B10"] = "OLD INVESTOR"
    bbnt["C10"] = "Chức vụ:"
    bbnt["A11"] = "Đại diện tư vấn giám sát: OLD SUPERVISOR ORG"
    bbnt["A12"] = "Ông/Bà: "
    bbnt["B12"] = "OLD SUPERVISOR"
    bbnt["C12"] = "Chức vụ:"
    bbnt["A13"] = "Ông/Bà: "
    bbnt["B13"] = "OLD SUPERVISOR 2"
    bbnt["C13"] = "Chức vụ:"
    bbnt["A14"] = "Đại diện đơn vị thi công: OLD CONTRACTOR ORG"
    bbnt["A15"] = "Ông/Bà: "
    bbnt["B15"] = "OLD CONTRACTOR"
    bbnt["C15"] = "Chức vụ:"
    bbnt["A16"] = "Ông/Bà: "
    bbnt["C16"] = "Chức vụ:"
    bbnt["A17"] = "Thời gian nghiệm thu:"
    bbnt["A18"] = "Bắt đầu: "
    bbnt["B18"] = "21h00"
    bbnt["C18"] = "Ngày "
    bbnt["D18"] = "2026-10-13"
    bbnt["A19"] = "Kết thúc:"
    bbnt["B19"] = "22h00"
    bbnt["C19"] = "Ngày "
    bbnt["D19"] = "2026-10-13"
    bbnt["A20"] = "Đánh giá công việc xây dựng đã thực hiện"
    bbnt["A21"] = "Căn cứ nghiệm thu"
    bbnt["A22"] = "Stt"
    bbnt["B22"] = "Hồ sơ, tài liệu"
    bbnt["C22"] = "Mã hiệu tài liệu"
    bbnt["D22"] = "Kiểm tra"
    bbnt["F22"] = "Ghi chú"
    bbnt["D23"] = "Có"
    bbnt["E23"] = "Không"
    for index, row in enumerate(range(24, 31), start=1):
        bbnt[f"A{row}"] = index
        bbnt[f"B{row}"] = f"Item {index}"
        bbnt[f"D{row}"] = "☑"
        bbnt[f"E{row}"] = "□"
    bbnt["A31"] = "Về chất lượng công việc xây dựng"
    bbnt["A32"] = "So với thiết kế: Đảm bảo ☑ Không đảm bảo □"
    bbnt["A33"] = "So với yêu cầu, chỉ dẫn kỹ thuật: Đạt yêu cầu ☑ Không đạt yêu cầu □"
    bbnt["A34"] = "Ý kiến khác (nếu có)"
    bbnt["A35"] = "Kết luận"
    bbnt["A36"] = "   Đồng ý nghiệm thu, cho triển khai các công việc tiếp theo ☑"
    bbnt["A37"] = "   Đồng ý nghiệm thu với điều kiện: "
    bbnt["A39"] = "Đại diện Chủ đầu tư                                  Đại diện TVGS"
    bbnt["E39"] = "Đại diện Nhà thầu thi công"
    bbnt["A43"] = "      OLD INVESTOR                                 OLD SUPERVISOR                                OLD CONTRACTOR"

    bblm["A12"] = "Ông/Bà: OLD SUPERVISOR                    Chức vụ:  TVGS"
    bblm["A13"] = "Ông/Bà: OLD SUPERVISOR 2                  Chức vụ:  TVGS"
    bblm["A15"] = "Ông/Bà: OLD CONTRACTOR                    Chức vụ:  CBKT"
    bblm["A16"] = "Ông/Bà: OLD CONTRACTOR 2                  Chức vụ:  CBKT"

    # A drawing/media part proves the zip-preserving exporter does not drop
    # logos the way a plain openpyxl save would.
    image_path = path.parent / "pixel.png"
    Image.new("RGB", (4, 4), (200, 0, 0)).save(image_path)
    pyc.add_image(XLImage(str(image_path)), "L1")

    wb.save(path)
    return path


@pytest.fixture()
def template_path(tmp_path, monkeypatch):
    if CANONICAL_TEMPLATE.is_file():
        destination = tmp_path / "acceptance-template.xlsx"
        shutil.copyfile(CANONICAL_TEMPLATE, destination)
    else:
        destination = _make_synthetic_template(tmp_path / "synthetic-template.xlsx")
    monkeypatch.setenv("ACCEPTANCE_TEMPLATE", str(destination))
    return destination


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def actor():
    return type("User", (), {"id": "human-confirmer", "role": "project_manager"})()


@pytest.fixture()
def client(db_engine, actor, tmp_path, monkeypatch):
    monkeypatch.setenv("ACCEPTANCE_STORAGE", str(tmp_path / "storage"))
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_project_member] = lambda project_id: actor
    app.dependency_overrides[require_editor] = lambda project_id: actor
    app.dependency_overrides[require_confirmer] = lambda project_id: actor
    with TestClient(app) as test_client:
        test_client.actor = actor
        test_client.SessionLocal = SessionLocal
        yield test_client


def request_payload(**overrides):
    payload = {
        "number": "32",
        "status": "draft",
        "project_name": "Công trình thử nghiệm",
        "client": "Chủ đầu tư thử nghiệm",
        "project_location": "Vị trí công trình thử nghiệm",
        "location": "Phân đoạn 1 - Cầu chính",
        "request_date": "2026-11-11",
        "inspection_time": "15h00",
        "content": "Nội dung nghiệm thu thử nghiệm",
        "subject": "Đối tượng nghiệm thu thử nghiệm",
        "field": "construction",
        "urgency": "normal",
        "requested_by_name": "Người yêu cầu",
        "supervisor_name": "Người giám sát",
        "investor_name": "Người chủ đầu tư",
        "contractor_org": "Nhà thầu thử nghiệm",
        "supervisor_org": "Tư vấn thử nghiệm",
        "investor_org": "Chủ đầu tư thử nghiệm",
        "notes": "Ghi chú",
    }
    payload.update(overrides)
    return payload


def record_payload(request_id, **overrides):
    payload = {
        "request_id": request_id,
        "record_date": "2026-11-11",
        "start_time": "15h00",
        "end_time": "16h20",
        "design_compliance": "yes",
        "technical_compliance": "yes",
        "other_notes": "Không có",
        "conclusion_note": "",
        "participants": [
            {
                "role": "investor",
                "person_name": "Người chủ đầu tư",
                "organization": "Chủ đầu tư thử nghiệm",
                "position": "Giám đốc",
                "sort_order": 0,
            },
            {
                "role": "supervisor",
                "person_name": "Người giám sát",
                "organization": "Tư vấn thử nghiệm",
                "position": "TVGS",
                "sort_order": 1,
            },
            {
                "role": "contractor",
                "person_name": "Người yêu cầu",
                "organization": "Nhà thầu thử nghiệm",
                "position": "CBKT",
                "sort_order": 2,
            },
        ],
        "checklist": [
            {"item": f"Hạng mục {index}", "state": "yes", "evidence_refs": [], "sort_order": index}
            for index in range(1, 8)
        ],
    }
    payload.update(overrides)
    return payload


def create_request(client, **overrides):
    response = client.post("/api/v1/projects/p1/acceptance-requests", json=request_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def create_record(client, request_id, **overrides):
    response = client.post(
        "/api/v1/projects/p1/acceptance-records", json=record_payload(request_id, **overrides)
    )
    assert response.status_code == 201, response.text
    return response.json()


def seed_work_item(client, project_id="p1", code="W-TEST", name="Hạng mục thử nghiệm"):
    with client.SessionLocal() as db:
        item = WorkItem(project_id=project_id, code=code, name=name)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id


def seed_photo(
    client,
    project_id="p1",
    *,
    confirmed_caption=None,
    category=None,
    filename="evidence.jpg",
    report_id=None,
):
    with client.SessionLocal() as db:
        photo = SitePhoto(
            project_id=project_id,
            report_id=report_id,
            original_path=f"/tmp/opencode/{filename}",
            sha256="0" * 64,
            confirmed_caption=confirmed_caption,
            category=category,
            filename=filename,
            mime_type="image/jpeg",
            size_bytes=4,
        )
        db.add(photo)
        db.commit()
        db.refresh(photo)
        return photo.id


def seed_daily_report(
    client,
    project_id="p1",
    *,
    report_date="2026-11-11",
    status="draft",
    notes="Báo cáo ngày thử nghiệm",
):
    parsed = date.fromisoformat(report_date) if isinstance(report_date, str) else report_date
    with client.SessionLocal() as db:
        report = DailyReport(
            project_id=project_id,
            report_date=parsed,
            status=status,
            notes=notes,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report.id


def seed_source_document(
    client,
    project_id="p1",
    *,
    original_name="Tài liệu thử nghiệm.pdf",
    document_key=None,
):
    document_key = document_key or f"doc-{uuid.uuid4().hex}"
    with client.SessionLocal() as db:
        document = SourceDocument(
            project_id=project_id,
            type="drawing",
            original_name=original_name,
            document_key=document_key,
            original_path=f"/tmp/opencode/{document_key}.pdf",
            sha256=uuid.uuid4().hex * 2,
            status="ready",
            page_count=2,
            mime_type="application/pdf",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document.id


def seed_document_page(
    client,
    document_id,
    project_id="p1",
    *,
    page_number=1,
):
    with client.SessionLocal() as db:
        page = DocumentPage(
            project_id=project_id,
            document_id=document_id,
            page_number=page_number,
            extraction_method="text",
            text="Trang tài liệu thử nghiệm",
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        return page.id
