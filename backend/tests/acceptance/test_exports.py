"""Excel export tests: copy template, replace validated cells, scrub old data."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from app.acceptance.models import AcceptanceGeneratedDocument
from conftest import create_record, create_request

OLD_PERSONNEL_CELLS = {
    "PYC": ("A20", "E20", "H20"),
    "BBNT": ("B10", "B12", "B13", "B15", "A43"),
    "PYC (2)": ("A20", "E20", "H20"),
}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sheet_xml(path, sheet_name):
    with zipfile.ZipFile(path) as archive:
        workbook = archive.read("xl/workbook.xml").decode("utf-8")
        rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        m = re.search(rf'<sheet[^>]*name="{re.escape(sheet_name)}"[^>]*r:id="([^"]+)"', workbook)
        assert m, sheet_name
        rid = m.group(1)
        rel = re.search(rf'<Relationship[^>]*Id="{re.escape(rid)}"[^>]*Target="([^"]+)"', rels)
        assert rel, rid
        target = rel.group(1).lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        return archive.read(target).decode("utf-8")


def _old_personnel(template):
    wb = openpyxl.load_workbook(template, data_only=False)
    names = set()
    for sheet_name, cells in OLD_PERSONNEL_CELLS.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        for coord in cells:
            value = ws[coord].value
            if isinstance(value, str) and value.strip():
                names.add(value.strip())
                for part in re.split(r"\s{2,}", value):
                    part = part.strip()
                    if len(part) > 3:
                        names.add(part)
    return names


def _export(client, source, kind):
    url = (
        f"/api/v1/projects/p1/acceptance-requests/{source['id']}/exports"
        if kind == "pyc"
        else f"/api/v1/projects/p1/acceptance-records/{source['id']}/exports"
    )
    response = client.post(url, json={"kind": kind, "format": "xlsx"})
    assert response.status_code == 201, response.text
    return response.json()


def _download(client, exported, tmp_path):
    response = client.get(exported["download_url"])
    assert response.status_code == 200, response.text
    path = tmp_path / f"export-{exported['id']}.xlsx"
    path.write_bytes(response.content)
    return path


def test_template_fixture_uses_repo_canonical_not_downloads(template_path):
    from conftest import CANONICAL_TEMPLATE

    assert "Downloads" not in str(CANONICAL_TEMPLATE)
    if CANONICAL_TEMPLATE.is_file():
        assert _sha(template_path) == _sha(CANONICAL_TEMPLATE)
    else:
        assert "synthetic" in template_path.name


def test_pyc_export_replaces_validated_cells_and_preserves_formatting(
    client, template_path, tmp_path
):
    template_hash = _sha(template_path)
    request = create_request(client)
    exported = _export(client, request, "pyc")
    assert exported["kind"] == "pyc"
    assert exported["template_sha256"] == template_hash
    path = _download(client, exported, tmp_path)

    assert _sha(template_path) == template_hash, "source template must not be modified"
    wb = openpyxl.load_workbook(path)
    ws = wb["PYC"]
    assert ws["C1"].value == "DỰ ÁN: Công trình thử nghiệm"
    assert ws["C2"].value == "CHỦ ĐẦU TƯ: Chủ đầu tư thử nghiệm"
    assert ws["C3"].value == "ĐỊA ĐIỂM: Vị trí công trình thử nghiệm"
    assert ws["B6"].value == 32
    assert ws["B7"].value == "Phân đoạn 1 - Cầu chính"
    assert ws["B10"].value.date() == date(2026, 11, 11)
    assert ws["D10"].value == "15h00"
    assert ws["E10"].value == "Nội dung nghiệm thu thử nghiệm tại  Đối tượng nghiệm thu thử nghiệm"
    assert ws["H10"].value == "☑"
    assert ws["I10"].value == "□"
    assert ws["K10"].value == "□"
    assert ws["D14"].value == "☑"
    assert ws["D15"].value == "□"
    assert ws["D16"].value == "□"
    assert ws["A20"].value == "Người yêu cầu"
    assert ws["E20"].value == "Người giám sát"
    assert ws["H20"].value == "Người chủ đầu tư"

    # Formatting anchors: merged ranges, widths/heights, print area.
    template_wb = openpyxl.load_workbook(template_path)
    template_ws = template_wb["PYC"]
    assert [str(r) for r in ws.merged_cells.ranges] == [
        str(r) for r in template_ws.merged_cells.ranges
    ]
    assert {k: v.width for k, v in ws.column_dimensions.items()} == {
        k: v.width for k, v in template_ws.column_dimensions.items()
    }
    assert ws.print_area == template_ws.print_area
    assert ws.page_setup.scale == template_ws.page_setup.scale
    # Target style ids are preserved.
    for coord in ("C1", "B6", "A20", "E20", "H20", "D14", "D15", "D16"):
        assert ws[coord].style_id == template_ws[coord].style_id
        assert ws[coord].font.name == template_ws[coord].font.name
        assert ws[coord].border.left.style == template_ws[coord].border.left.style

    # Package parts a plain openpyxl save would drop.
    with zipfile.ZipFile(template_path) as source, zipfile.ZipFile(path) as output:
        source_parts = set(source.namelist())
        output_parts = set(output.namelist())
        # The exporter always drops a stale calcChain so Excel rebuilds it.  The
        # canonical template may or may not contain one (LibreOffice removes it
        # on save), so only assert the removal when the source actually had it.
        assert "xl/calcChain.xml" not in output_parts
        if "xl/calcChain.xml" in source_parts:
            assert source_parts - output_parts == {"xl/calcChain.xml"}
        else:
            assert source_parts - output_parts == set()
        for prefix in ("xl/media/", "xl/drawings/", "xl/printerSettings/"):
            original = {n: source.read(n) for n in source_parts if n.startswith(prefix)}
            produced = {n: output.read(n) for n in output_parts if n.startswith(prefix)}
            assert produced == original, prefix
        assert source.read("xl/styles.xml") == output.read("xl/styles.xml")
        assert source.read("xl/theme/theme1.xml") == output.read("xl/theme/theme1.xml")

    # A standalone PYC export leaves its companion BBNT sheet blank and safe.
    bbnt = openpyxl.load_workbook(path)["BBNT"]
    assert bbnt["A36"].value.endswith("□")
    assert "☑" not in bbnt["A36"].value
    assert bbnt["A37"].value == "   Đồng ý nghiệm thu với điều kiện: "

    # Old personnel must not survive in any PYC/BBNT worksheet XML.
    old_names = _old_personnel(template_path)
    xml = _sheet_xml(path, "PYC") + _sheet_xml(path, "BBNT") + _sheet_xml(path, "PYC (2)")
    for name in old_names:
        assert name not in xml, name


def test_pyc_export_has_no_old_defaults_when_fields_missing(client, template_path, tmp_path):
    request = create_request(
        client,
        content=None,
        subject=None,
        location=None,
        request_date=None,
        inspection_time=None,
        field=None,
        urgency=None,
        requested_by_name=None,
        supervisor_name=None,
        investor_name=None,
    )
    exported = _export(client, request, "pyc")
    path = _download(client, exported, tmp_path)
    ws = openpyxl.load_workbook(path)["PYC"]
    for coord in ("A20", "E20", "H20", "B7", "B10", "D10", "E10", "F6"):
        assert ws[coord].value in (None, ""), coord
    assert ws["D14"].value == "□"
    assert ws["D15"].value == "□"
    assert ws["D16"].value == "□"
    assert ws["H10"].value == "□"
    assert ws["I10"].value == "□"
    assert ws["K10"].value == "□"


def test_bbnt_export_requires_human_confirmation(client, tmp_path):
    request = create_request(client)
    record = create_record(client, request["id"])
    response = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports",
        json={"kind": "bbnt", "format": "xlsx"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "record_not_confirmed"


def test_confirmed_bbnt_export_replaces_personnel_checkboxes_and_conclusions(
    client, template_path, tmp_path
):
    request = create_request(client)
    record = create_record(client, request["id"])
    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "conditional", "conclusion_note": "Bổ sung hồ sơ thí nghiệm"},
    )
    assert confirmed.status_code == 200, confirmed.text

    exported = _export(client, confirmed.json(), "bbnt")
    path = _download(client, exported, tmp_path)
    ws = openpyxl.load_workbook(path)["BBNT"]

    assert ws["B5"].value == 32
    assert ws["B6"].value == "Phân đoạn 1 - Cầu chính"
    assert ws["B10"].value == "Người chủ đầu tư"
    assert ws["D10"].value == "Giám đốc"
    assert ws["B12"].value == "Người giám sát"
    assert ws["D12"].value == "TVGS"
    assert ws["B15"].value == "Người yêu cầu"
    assert ws["D15"].value == "CBKT"
    assert ws["B18"].value == "15h00"
    assert ws["B19"].value == "16h20"
    assert ws["D18"].value.date() == date(2026, 11, 11)
    assert ws["D19"].value.date() == date(2026, 11, 11)
    assert ws["D24"].value == "☑"
    assert ws["E24"].value == "□"
    assert ws["D25"].value == "☑"
    assert ws["E25"].value == "□"
    assert "☑" in ws["A32"].value and "□" in ws["A32"].value
    assert "☑" in ws["A33"].value and "□" in ws["A33"].value
    assert ws["A34"].value == "Ý kiến khác (nếu có): Không có"
    assert ws["A36"].value.endswith("□")
    assert "Bổ sung hồ sơ thí nghiệm" in ws["A37"].value
    assert "Người chủ đầu tư" in ws["A43"].value
    assert "Người giám sát" in ws["A43"].value
    assert "Người yêu cầu" in ws["A43"].value

    old_names = _old_personnel(template_path)
    xml = _sheet_xml(path, "BBNT") + _sheet_xml(path, "PYC (2)")
    for name in old_names:
        assert name not in xml, name

    template_wb = openpyxl.load_workbook(template_path)
    template_ws = template_wb["BBNT"]
    assert [str(r) for r in ws.merged_cells.ranges] == [
        str(r) for r in template_ws.merged_cells.ranges
    ]
    assert ws.print_area == template_ws.print_area
    assert ws.page_setup.scale == template_ws.page_setup.scale


def test_record_export_can_produce_pyc_and_history(client, tmp_path):
    request = create_request(client)
    record = create_record(client, request["id"])
    exported = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports",
        json={"kind": "pyc", "format": "xlsx"},
    )
    assert exported.status_code == 201, exported.text

    history = client.get(f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports")
    assert history.status_code == 200
    assert len(history.json()) == 1

    all_exports = client.get("/api/v1/projects/p1/acceptance-exports")
    assert all_exports.status_code == 200
    assert len(all_exports.json()) == 1

    download = client.get(exported.json()["download_url"])
    assert download.status_code == 200
    assert len(download.content) > 1000


def test_record_pyc_export_resets_bbnt_sheet_to_a_blank_safe_state(
    client, template_path, tmp_path
):
    """A PYC-only export must not carry over the template's BBNT conclusions."""

    request = create_request(client)
    record = create_record(client, request["id"])
    exported = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports",
        json={"kind": "pyc", "format": "xlsx"},
    )
    assert exported.status_code == 201, exported.text
    path = _download(client, exported.json(), tmp_path)
    ws = openpyxl.load_workbook(path)["BBNT"]

    # Old approval conclusion is cleared, leaving unchecked boxes only.
    assert ws["A36"].value.endswith("□")
    assert "☑" not in ws["A36"].value
    assert ws["A37"].value == "   Đồng ý nghiệm thu với điều kiện: "
    assert ws["A32"].value is not None and "☑" not in ws["A32"].value
    assert ws["A33"].value is not None and "☑" not in ws["A33"].value

    # Old personnel, organisations and signature/sample values are cleared.
    for coord in ("B10", "D10", "B12", "D12", "B13", "D13", "B15", "D15", "B16", "D16", "A43"):
        assert ws[coord].value in (None, ""), coord
    for coord in ("A8", "A11", "A14"):
        assert "OLD" not in (ws[coord].value or ""), coord
    for row in range(24, 31):
        assert ws[f"D{row}"].value == "□"
        assert ws[f"E{row}"].value == "□"

    # PYC itself is filled from the request while the hidden PYC copy is scrubbed.
    pyc = openpyxl.load_workbook(path)["PYC"]
    assert pyc["A20"].value == "Người yêu cầu"
    old_names = _old_personnel(template_path)
    xml = _sheet_xml(path, "BBNT") + _sheet_xml(path, "PYC (2)")
    for name in old_names:
        assert name not in xml, name


def _libreoffice_available() -> bool:
    return bool(shutil.which("libreoffice") or shutil.which("soffice"))


@pytest.mark.skipif(not _libreoffice_available(), reason="LibreOffice headless is not installed")
def test_pdf_export_uses_validated_workbook_and_preserves_template(
    client, template_path, tmp_path
):
    template_hash = _sha(template_path)
    request = create_request(client)
    response = client.post(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/exports",
        json={"kind": "pyc", "format": "pdf"},
    )
    assert response.status_code == 201, response.text
    exported = response.json()
    assert exported["format"] == "pdf"
    assert exported["template_sha256"] == template_hash

    download = client.get(exported["download_url"])
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")
    assert len(download.content) > 1000
    pdf_path = tmp_path / "acceptance.pdf"
    pdf_path.write_bytes(download.content)
    assert _sha(pdf_path) == exported["sha256"]

    # The original template is untouched, and the validated workbook used for
    # conversion is retained in export history metadata.
    assert _sha(template_path) == template_hash
    with client.SessionLocal() as db:
        document = db.get(AcceptanceGeneratedDocument, exported["id"])
        assert document is not None
        metadata = json.loads(document.metadata_json)
        workbook = Path(metadata["workbook_path"])
        assert workbook.is_file()
        assert metadata["workbook_sha256"]
        assert document.format == "pdf"
    ws = openpyxl.load_workbook(workbook)["PYC"]
    assert ws["B6"].value == 32
    assert ws["A20"].value == "Người yêu cầu"


@pytest.mark.skipif(not _libreoffice_available(), reason="LibreOffice headless is not installed")
def test_confirmed_bbnt_can_export_pdf(client, template_path, tmp_path):
    request = create_request(client)
    record = create_record(client, request["id"])
    confirmed = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/confirm",
        json={"result": "approved"},
    )
    assert confirmed.status_code == 200, confirmed.text
    response = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports",
        json={"kind": "bbnt", "format": "pdf"},
    )
    assert response.status_code == 201, response.text
    exported = response.json()
    assert exported["format"] == "pdf"

    download = client.get(exported["download_url"])
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")

    with client.SessionLocal() as db:
        document = db.get(AcceptanceGeneratedDocument, exported["id"])
        metadata = json.loads(document.metadata_json)
        workbook = Path(metadata["workbook_path"])
        assert workbook.is_file()
    ws = openpyxl.load_workbook(workbook)["BBNT"]
    assert ws["B15"].value == "Người yêu cầu"
    assert "☑" in ws["A36"].value
    assert _sha(template_path) == exported["template_sha256"]


def test_bbnt_pdf_export_still_requires_confirmation(client):
    request = create_request(client)
    record = create_record(client, request["id"])
    response = client.post(
        f"/api/v1/projects/p1/acceptance-records/{record['id']}/exports",
        json={"kind": "bbnt", "format": "pdf"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "record_not_confirmed"


def test_pdf_export_reports_missing_converter(client, monkeypatch):
    monkeypatch.setenv("ACCEPTANCE_LIBREOFFICE", "/nonexistent/libreoffice")
    request = create_request(client)
    response = client.post(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/exports",
        json={"kind": "pyc", "format": "pdf"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "pdf_converter_unavailable"
    assert "LibreOffice" in response.json()["detail"]

    with client.SessionLocal() as db:
        assert db.query(AcceptanceGeneratedDocument).count() == 0


def test_missing_template_is_reported(client, tmp_path, monkeypatch):
    request = create_request(client)
    monkeypatch.setenv("ACCEPTANCE_TEMPLATE", str(tmp_path / "does-not-exist.xlsx"))
    response = client.post(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/exports",
        json={"kind": "pyc", "format": "xlsx"},
    )
    assert response.status_code == 500
    assert response.json()["code"] == "template_missing"


def test_invalid_template_is_reported(client, tmp_path, monkeypatch):
    from openpyxl import Workbook

    bad = tmp_path / "not-acceptance.xlsx"
    workbook = Workbook()
    workbook.active.title = "Other"
    workbook.save(bad)
    monkeypatch.setenv("ACCEPTANCE_TEMPLATE", str(bad))

    request = create_request(client)
    response = client.post(
        f"/api/v1/projects/p1/acceptance-requests/{request['id']}/exports",
        json={"kind": "pyc", "format": "xlsx"},
    )
    assert response.status_code == 500
    assert response.json()["code"] == "template_invalid"
