import io
import json
import zipfile


def _seed_report(client, status="reviewed", date="2026-11-11"):
    payload = {
        "status": status,
        "notes": "note",
        "site_notes": {
            "weather": "Nắng nhẹ",
            "materials": "Thép D16",
            "equipment": None,
            "incidents": None,
            "difficulties": "Mưa chiều",
            "safety": "Đủ PPE",
            "recommendations": None,
            "other": None,
        },
        "manpower": [
            {"group_name": "Workers", "count": 0},
            {"group_name": "Eng", "count": None},
            {"group_name": "Supervisors", "count": 5},
        ],
        "work_logs": [
            {
                "work_item_id": "w1",
                "location": "Span 1",
                "component": "Concrete",
                "quantity": 2.5,
                "unit": "m3",
                "status": "done",
            },
            {
                "work_item_id": "w1",
                "location": "Span 2",
                "component": "Formwork",
                "quantity": None,
                "unit": "m2",
                "status": "in_progress",
            },
        ],
        "next_day_plans": [
            {"plan_date": "2026-11-12", "description": "Continue", "manpower": "5"},
            {
                "plan_date": "2026-11-12",
                "work_item_id": "w1",
                "description": None,
            },
        ],
    }
    r = client.put(f"/api/v1/projects/p1/daily-reports/{date}", json=payload)
    assert r.status_code == 200, r.text
    report = r.json()

    confirmed = client.post(
        "/api/v1/projects/p1/photos",
        files=[("files", ("p.png", io.BytesIO(b"confirmed-photo"), "image/png"))],
        data={
            "report_id": report["id"],
            "confirmed_caption": "Site photo",
            "category": "progress",
            "work_item_ids": "w1",
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    unconfirmed = client.post(
        "/api/v1/projects/p1/photos",
        files=[("files", ("u.png", io.BytesIO(b"unconfirmed-photo"), "image/png"))],
        data={
            "report_id": report["id"],
            "suggested_caption": "AI suggested only",
        },
    )
    assert unconfirmed.status_code == 201, unconfirmed.text
    return report


def test_export_requires_reviewed_report(client):
    _seed_report(client, status="draft")
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports",
        json={"format": "zalo"},
    )
    assert r.status_code == 409


def test_export_zalo_contains_zero_null_and_never_auto_sends(client):
    _seed_report(client)
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports",
        json={"format": "zalo"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    preview = body["preview_text"]
    assert preview.startswith("Test project\nNgày: 11/11/2026")
    assert "1. Nhân lực" in preview
    assert "2. Công việc thực hiện" in preview
    assert "3. Dự kiến công việc ngày 12/11/2026" in preview
    assert "4. Hình ảnh" in preview
    assert "Workers" in preview
    assert ": 0" in preview
    assert "chưa rõ" in preview
    assert "Nhóm có 0 người: Workers" in preview
    assert "Tổng nhân lực đã biết: 5" in preview
    assert "Ghi chú hiện trường:" in preview
    assert "- Thời tiết: Nắng nhẹ" in preview
    assert "- Vật tư: Thép D16" in preview
    assert "- Khó khăn: Mưa chiều" in preview
    assert "- An toàn: Đủ PPE" in preview
    assert "Sự cố" not in preview
    assert "- Work item 1 - Span 1 - Concrete: 2.5 m3 (Hoàn thành)" in preview
    # A missing quantity must stay absent, not become an invented number.
    assert "- Work item 1 - Span 2 - Formwork (Đang làm)" in preview
    assert "chưa rõ KL" not in preview
    # All plans share one date: it belongs in the heading, not each item.
    plan_section = preview.split("3. Dự kiến công việc", 1)[1].split(
        "4. Hình ảnh", 1
    )[0]
    assert "Work item 1" in plan_section
    assert "- 12/11/2026:" not in plan_section
    assert "Site photo" in preview
    assert "AI suggested only" not in preview
    assert "Không tự động gửi Zalo" in preview
    assert body["auto_send"] is False
    assert body["snapshot_sha256"]
    assert body["download_url"]


def test_export_pdf_docx_zip_download(client):
    _seed_report(client)
    for fmt in ("pdf", "docx", "zip"):
        r = client.post(
            "/api/v1/projects/p1/daily-reports/2026-11-11/exports",
            json={"format": fmt},
        )
        assert r.status_code == 201, (fmt, r.text)
        assert r.json()["auto_send"] is False
        download = client.get(r.json()["download_url"])
        assert download.status_code == 200
        assert len(download.content) > 0
        if fmt == "pdf":
            assert download.content.startswith(b"%PDF")
            import fitz

            with fitz.open(stream=download.content, filetype="pdf") as pdf:
                text = "".join(page.get_text() for page in pdf)
            assert "11/11/2026" in text
            assert "Workers" in text
        if fmt == "docx":
            assert download.content.startswith(b"PK")
        if fmt == "zip":
            assert download.content.startswith(b"PK")


def test_zip_contains_snapshot_evidence_and_only_confirmed_photos(client):
    _seed_report(client)
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports",
        json={"format": "zip"},
    )
    assert r.status_code == 201
    download = client.get(r.json()["download_url"])
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        names = archive.namelist()
        assert "snapshot.json" in names
        assert "zalo.txt" in names
        assert "report.pdf" in names
        assert "report.docx" in names
        photo_names = [name for name in names if name.startswith("photos/")]
        assert len(photo_names) == 1

        snapshot = json.loads(archive.read("snapshot.json"))
        assert snapshot["status"] == "reviewed"
        assert snapshot["title"] == "Test project"
        assert snapshot["report_date_display"] == "11/11/2026"
        assert snapshot["site_notes"]["weather"] == "Nắng nhẹ"
        assert snapshot["site_notes"]["incidents"] is None
        assert snapshot["auto_send"] is False
        assert snapshot["photo_summary"] == {
            "evidence_count": 1,
            "omitted_unconfirmed_count": 1,
        }
        assert all(
            item["work_item_name"] == "Work item 1"
            for item in snapshot["work_logs"]
        )
        assert any(
            item["work_item_name"] is None for item in snapshot["next_day_plans"]
        )
        plan_with_item = [
            item for item in snapshot["next_day_plans"] if item["work_item_id"] == "w1"
        ][0]
        assert plan_with_item["work_item_name"] == "Work item 1"
        counts = {item["group_name"]: item["count"] for item in snapshot["manpower"]}
        assert counts["Workers"] == 0
        assert counts["Eng"] is None
        assert snapshot["manpower_summary"]["known_total"] == 5
        assert snapshot["manpower_summary"]["unknown_groups"] == ["Eng"]
        assert snapshot["manpower_summary"]["zero_groups"] == ["Workers"]
        assert snapshot["photos"][0]["confirmed_caption"] == "Site photo"
        assert snapshot["photos"][0]["gps_confirmed"] is False


def test_export_docx_is_readable_unicode(client):
    _seed_report(client)
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports",
        json={"format": "docx"},
    )
    assert r.status_code == 201
    download = client.get(r.json()["download_url"])
    from docx import Document

    document = Document(io.BytesIO(download.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Test project" in text
    assert "Ngày: 11/11/2026" in text
    assert "Không tự động gửi Zalo" in text


def test_export_history(client):
    _seed_report(client)
    first = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports", json={"format": "zalo"}
    )
    second = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports", json={"format": "pdf"}
    )
    assert first.status_code == 201 and second.status_code == 201
    r = client.get("/api/v1/projects/p1/daily-reports/2026-11-11/exports")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert {item["format"] for item in body} == {"zalo", "pdf"}
    assert all(item["auto_send"] is False for item in body)
    assert all(item["snapshot_sha256"] for item in body)


def test_export_and_history_project_scoped(client):
    _seed_report(client)
    assert (
        client.post(
            "/api/v1/projects/p2/daily-reports/2026-11-11/exports",
            json={"format": "zalo"},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/projects/p2/daily-reports/2026-11-11/exports").status_code == 404
    # Generated document from p1 is not downloadable through p2.
    made = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports", json={"format": "zalo"}
    ).json()
    doc_id = made["id"]
    assert (
        client.get(f"/api/v1/projects/p2/generated-documents/{doc_id}/download").status_code
        == 404
    )


def test_export_missing_report(client):
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2020-01-01/exports",
        json={"format": "zalo"},
    )
    assert r.status_code == 404


def test_invalid_export_format_rejected(client):
    _seed_report(client)
    r = client.post(
        "/api/v1/projects/p1/daily-reports/2026-11-11/exports",
        json={"format": "exe"},
    )
    assert r.status_code == 422
