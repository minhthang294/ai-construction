import io

from .conftest import add_page_extraction, make_scanned_pdf, make_text_pdf, upload_pdf


def test_digital_pdf_extracts_each_page_with_hash_version(client, digital_document):
    assert digital_document["status"] == "pending"
    assert len(digital_document["sha256"]) == 64
    assert digital_document["version"] == 1
    assert digital_document["is_current"] is True

    detail = client.get(
        f"/api/v1/projects/p1/documents/{digital_document['id']}"
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["status"] == "ready"
    assert body["page_count"] == 2
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert body["pages"][0]["extraction_method"] == "text"
    assert body["pages"][0]["drawing_number"] == "BV-01"
    assert body["pages"][0]["revision"] == "A"

    page = client.get(
        f"/api/v1/projects/p1/documents/{digital_document['id']}/pages/1"
    )
    assert page.status_code == 200, page.text
    assert "Bridge abutment" in page.json()["text"]
    assert page.json()["ocr_confidence"] is None

    original = client.get(
        f"/api/v1/projects/p1/documents/{digital_document['id']}/original"
    )
    assert original.status_code == 200
    assert original.content.startswith(b"%PDF-")


def test_duplicate_same_bytes_is_idempotent_and_new_bytes_create_version(
    client, session_factory
):
    original_bytes = make_text_pdf(["Asbestos membrane old revision"])
    first = upload_pdf(client, filename="same-name.pdf", data=original_bytes)
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    first_document = client.get(f"/api/v1/projects/p1/documents/{first_id}").json()
    add_page_extraction(
        session_factory,
        project_id="p1",
        document_id=first_id,
        page_id=first_document["pages"][0]["id"],
        page_number=1,
        extraction={
            "page_type": "specification",
            "title": "Asbestos membrane",
            "summary": "Asbestos membrane old revision.",
            "key_values": [
                {
                    "name": "asbestos membrane",
                    "value": "old revision",
                    "quote": "Asbestos membrane old revision",
                }
            ],
            "table_rows": [],
            "warnings": [],
            "confidence": 0.8,
        },
    )

    duplicate = upload_pdf(client, filename="same-name.pdf", data=original_bytes)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["id"] == first_id
    assert duplicate.json()["deduplicated"] is True

    second = upload_pdf(client, filename="same-name.pdf", data=make_text_pdf(["Steel anchor new revision"]))
    assert second.status_code == 201, second.text
    assert second.json()["version"] == 2
    assert second.json()["is_current"] is True
    second_document = client.get(
        f"/api/v1/projects/p1/documents/{second.json()['id']}"
    ).json()
    add_page_extraction(
        session_factory,
        project_id="p1",
        document_id=second.json()["id"],
        page_id=second_document["pages"][0]["id"],
        page_number=1,
        extraction={
            "page_type": "specification",
            "title": "Steel anchor",
            "summary": "Steel anchor new revision.",
            "key_values": [
                {
                    "name": "steel anchor",
                    "value": "new revision",
                    "quote": "Steel anchor new revision",
                }
            ],
            "table_rows": [],
            "warnings": [],
            "confidence": 0.8,
        },
    )

    history = client.get("/api/v1/projects/p1/documents").json()
    assert len(history) == 2
    old = next(item for item in history if item["id"] == first_id)
    assert old["is_current"] is False
    assert old["is_effective"] is True
    assert old["version"] == 1
    new = next(item for item in history if item["id"] == second.json()["id"])
    assert new["is_current"] is True
    assert new["is_effective"] is False

    # Effective scope keeps the old revision until an explicit confirmation.
    old_search = client.post(
        "/api/v1/projects/p1/ai/search",
        json={"query": "asbestos membrane"},
    ).json()
    assert old_search["has_sources"] is True
    assert old_search["citations"][0]["version"] == 1

    new_effective = client.post(
        "/api/v1/projects/p1/ai/search",
        json={"query": "steel anchor"},
    ).json()
    assert new_effective["has_sources"] is False

    history_search = client.post(
        "/api/v1/projects/p1/ai/search",
        json={"query": "steel anchor", "scope": "history"},
    ).json()
    assert history_search["has_sources"] is True
    assert history_search["citations"][0]["version"] == 2

    effective_chat = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "steel anchor"},
    ).json()
    assert effective_chat["no_source"] is True
    history_chat = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={"message": "steel anchor", "scope": "history"},
    ).json()
    assert history_chat["no_source"] is False
    assert history_chat["citations"][0]["version"] == 2

    versions = client.get(
        f"/api/v1/projects/p1/documents/{first_id}/versions"
    ).json()
    assert [item["version"] for item in versions] == [2, 1]

    confirmed = client.post(
        f"/api/v1/projects/p1/documents/{second.json()['id']}/effective",
        json={"change_note": "Ban hanh thay the"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["is_effective"] is True
    assert confirmed.json()["change_note"] == "Ban hanh thay the"
    assert confirmed.json()["effective_by"] == "test-user"

    after_confirm = client.post(
        "/api/v1/projects/p1/ai/search",
        json={"query": "steel anchor"},
    ).json()
    assert after_confirm["has_sources"] is True
    assert after_confirm["citations"][0]["version"] == 2

    compare = client.get(
        f"/api/v1/projects/p1/documents/{first_id}/compare/{second.json()['id']}"
    )
    assert compare.status_code == 200, compare.text
    body = compare.json()
    assert body["left"]["version"] == 1
    assert body["right"]["version"] == 2
    assert body["page_changes"]
    assert "không kết luận" in body["disclaimer"].casefold()


def test_scan_page_uses_ocr_fallback_and_records_confidence(client, ocr_engine):
    from app.engineering_ai.ocr import OcrResult

    ocr_engine.result = OcrResult(
        text="Drawing No: BV-02 Rev B. Concrete cover for pier is 60 mm.",
        confidence=0.86,
        engine="mock-ocr",
    )
    response = upload_pdf(client, filename="scan.pdf", data=make_scanned_pdf())
    assert response.status_code == 201, response.text

    detail = client.get(f"/api/v1/projects/p1/documents/{response.json()['id']}").json()
    assert detail["status"] == "ready", detail
    assert detail["pages"][0]["extraction_method"] == "ocr"
    assert detail["pages"][0]["ocr_confidence"] == 0.86
    assert detail["pages"][0]["needs_review"] is False
    assert ocr_engine.calls >= 1

    render = client.get(
        f"/api/v1/projects/p1/documents/{response.json()['id']}/pages/1/render"
    )
    assert render.status_code == 200
    assert render.content.startswith(b"\x89PNG")


def test_ingest_status_order_and_persistent_vectors(
    session_factory, ocr_engine, embedding_provider
):
    from app.engineering_ai import vector_store
    from app.engineering_ai.service import create_document, run_ingest_job

    data = make_text_pdf(["Concrete cover for abutment is 50 mm and grade C30."])
    with session_factory() as db:
        document, created = create_document(
            db,
            "p1",
            data,
            filename="status-vector.pdf",
            declared_mime="application/pdf",
            document_type="drawing",
            created_by="test-user",
        )
        assert created is True
        document_id = document.id

    statuses = []
    run_ingest_job(
        document_id,
        "p1",
        session_factory,
        ocr_engine,
        embedding_provider,
        10,
        "vie+eng",
        status_hook=statuses.append,
    )
    assert statuses == ["pending", "running", "ocr_completed", "indexing", "ready"]

    with session_factory() as db:
        from app.engineering_ai.models import DocumentChunk, SourceDocument

        document = db.get(SourceDocument, document_id)
        assert document.status == "ready"
        chunks = db.query(DocumentChunk).filter_by(document_id=document_id).all()
        assert chunks
        vector_rows = vector_store.knn(
            db,
            "p1",
            embedding_provider.name,
            embedding_provider.dim,
            embedding_provider.embed("concrete cover abutment"),
            5,
        )
        assert vector_rows
        assert {row[0] for row in vector_rows} & {chunk.id for chunk in chunks}

    before = None
    with session_factory() as db:
        from app.engineering_ai.models import DocumentPage

        before = (
            db.query(DocumentPage).filter_by(document_id=document_id).count(),
            db.query(DocumentChunk).filter_by(document_id=document_id).count(),
        )
    retry_statuses = []
    run_ingest_job(
        document_id,
        "p1",
        session_factory,
        ocr_engine,
        embedding_provider,
        10,
        "vie+eng",
        status_hook=retry_statuses.append,
    )
    assert retry_statuses == ["pending", "running", "ocr_completed", "indexing", "ready"]
    with session_factory() as db:
        from app.engineering_ai.models import DocumentPage

        after = (
            db.query(DocumentPage).filter_by(document_id=document_id).count(),
            db.query(DocumentChunk).filter_by(document_id=document_id).count(),
        )
    assert after == before



def test_native_table_and_section_chunking(client, session_factory):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 80), "1. VAT LIEU", fontsize=14)
    page.insert_text((72, 110), "Concrete grade C30 for abutment.", fontsize=10)
    columns = [72, 220, 360, 480]
    rows = [180, 205, 230]
    for x in columns:
        page.draw_line((x, rows[0]), (x, rows[-1]), color=(0, 0, 0), width=1)
    for y in rows:
        page.draw_line((columns[0], y), (columns[-1], y), color=(0, 0, 0), width=1)
    for row_index, values in enumerate(
        [["Item", "Value", "Unit"], ["Cover", "50", "mm"]]
    ):
        for column_index, value in enumerate(values):
            page.insert_text(
                (columns[column_index] + 3, rows[row_index] + 17),
                value,
                fontsize=9,
            )
    page.insert_text((72, 320), "2. THI CONG", fontsize=14)
    page.insert_text((72, 350), "Inspect formwork before pouring concrete.", fontsize=10)
    data = document.tobytes()
    document.close()

    response = upload_pdf(client, filename="table-heading.pdf", data=data)
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]
    detail = client.get(f"/api/v1/projects/p1/documents/{document_id}").json()
    assert detail["status"] == "ready"
    page_json = client.get(
        f"/api/v1/projects/p1/documents/{document_id}/pages/1"
    ).json()
    assert page_json["tables"]
    assert page_json["tables"][0]["rows"][1][1] == "50"

    with session_factory() as db:
        from app.engineering_ai.models import DocumentChunk

        chunks = (
            db.query(DocumentChunk)
            .filter_by(document_id=document_id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
    sections = {chunk.section for chunk in chunks}
    assert "1. VAT LIEU" in sections
    assert "2. THI CONG" in sections
    for chunk in chunks:
        assert not (
            "1. VAT LIEU" in chunk.text and "2. THI CONG" in chunk.text
        )


def test_ingest_and_search_fall_back_without_vector_store(
    client, monkeypatch, session_factory
):
    from app.engineering_ai import vector_store

    monkeypatch.setattr(vector_store, "available", lambda db: False)
    pdf = make_text_pdf(["Concrete cover for abutment is 50 mm."])
    response = upload_pdf(client, filename="fallback.pdf", data=pdf)
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]
    assert client.get(
        f"/api/v1/projects/p1/documents/{document_id}"
    ).json()["status"] == "ready"
    search = client.post(
        "/api/v1/projects/p1/ai/search",
        json={"query": "concrete cover abutment"},
    ).json()
    assert search["has_sources"] is True
    with session_factory() as db:
        from sqlalchemy import text

        vector_tables = db.execute(
            text("SELECT name FROM sqlite_master WHERE name LIKE 'vec_ea_%'")
        ).all()
    assert vector_tables == []


def test_vector_store_persists_across_engine_reopen(
    tmp_path, ocr_engine, embedding_provider
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.engineering_ai import vector_store
    from app.engineering_ai.models import Base
    from app.engineering_ai.service import create_document, run_ingest_job

    db_path = tmp_path / "persistent-vector.sqlite3"
    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with factory() as db:
        document, _ = create_document(
            db,
            "p1",
            make_text_pdf(["Concrete cover for abutment is 50 mm."]),
            filename="persistent.pdf",
            declared_mime="application/pdf",
            document_type="drawing",
            created_by="test-user",
        )
        document_id = document.id
    run_ingest_job(
        document_id,
        "p1",
        factory,
        ocr_engine,
        embedding_provider,
        10,
        "vie+eng",
    )
    engine.dispose()

    reopened = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    reopened_factory = sessionmaker(
        bind=reopened, autoflush=False, autocommit=False, future=True
    )
    with reopened_factory() as db:
        rows = vector_store.knn(
            db,
            "p1",
            embedding_provider.name,
            embedding_provider.dim,
            embedding_provider.embed("concrete cover"),
            5,
        )
    reopened.dispose()
    assert rows


def test_invalid_upload_rejected(client):
    response = client.post(
        "/api/v1/projects/p1/documents",
        files=[("file", ("not.pdf", io.BytesIO(b"hello"), "application/pdf"))],
    )
    assert response.status_code == 422


def test_oversized_pdf_is_rejected_before_unbounded_read(client, monkeypatch):
    monkeypatch.setenv("ENGINEERING_AI_MAX_PDF_BYTES", "64")
    payload = b"%PDF-1.7\n" + b"x" * 60  # 69 bytes > configured limit
    response = client.post(
        "/api/v1/projects/p1/documents",
        files=[("file", ("too-large.pdf", io.BytesIO(payload), "application/pdf"))],
    )
    assert response.status_code == 413, response.text
    assert "dung lượng" in response.json()["detail"]


def test_scan_without_ocr_text_marks_review_and_never_invents_content(client, ocr_engine):
    from app.engineering_ai.ocr import NullOcrEngine

    ocr_engine.extract_text = NullOcrEngine().extract_text
    response = upload_pdf(client, filename="blank-scan.pdf", data=make_scanned_pdf())
    assert response.status_code == 201, response.text

    detail = client.get(f"/api/v1/projects/p1/documents/{response.json()['id']}").json()
    assert detail["status"] == "ready"
    page = client.get(
        f"/api/v1/projects/p1/documents/{response.json()['id']}/pages/1"
    ).json()
    assert page["extraction_method"] == "none"
    assert page["text"] in {None, ""}
    assert page["needs_review"] is True
    assert page["warnings"]

    search = client.post(
        "/api/v1/projects/p1/ai/search",
        json={"query": "concrete cover pier"},
    ).json()
    assert search["has_sources"] is False


def test_ingest_retry_is_idempotent(client, digital_document, session_factory):
    from sqlalchemy import text

    with session_factory() as db:
        first_pages = db.execute(text("SELECT COUNT(*) FROM engineering_ai_document_pages")).scalar_one()
        first_chunks = db.execute(text("SELECT COUNT(*) FROM engineering_ai_document_chunks")).scalar_one()
        first_fts = db.execute(text("SELECT COUNT(*) FROM engineering_ai_chunks_fts")).scalar_one()
    assert first_pages == 2
    assert first_chunks >= 2
    assert first_fts == first_chunks

    retry = client.post(
        f"/api/v1/projects/p1/documents/{digital_document['id']}/reingest"
    )
    assert retry.status_code == 202, retry.text

    with session_factory() as db:
        second_pages = db.execute(text("SELECT COUNT(*) FROM engineering_ai_document_pages")).scalar_one()
        second_chunks = db.execute(text("SELECT COUNT(*) FROM engineering_ai_document_chunks")).scalar_one()
        second_fts = db.execute(text("SELECT COUNT(*) FROM engineering_ai_chunks_fts")).scalar_one()
    assert second_pages == first_pages
    assert second_chunks == first_chunks
    assert second_fts == first_fts


def test_documents_are_project_scoped(client, digital_document):
    other_project = client.get(
        f"/api/v1/projects/p2/documents/{digital_document['id']}"
    )
    assert other_project.status_code == 404
    other_page = client.get(
        f"/api/v1/projects/p2/documents/{digital_document['id']}/pages/1"
    )
    assert other_page.status_code == 404
    other_original = client.get(
        f"/api/v1/projects/p2/documents/{digital_document['id']}/original"
    )
    assert other_original.status_code == 404
