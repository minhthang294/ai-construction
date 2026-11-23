from .conftest import add_source_document


def test_list_and_get_documents_are_project_scoped(client, session_factory):
    document = add_source_document(
        session_factory, suffix="bv01", original_name="BV-01.pdf"
    )
    other = add_source_document(
        session_factory, project_id="p2", suffix="bv02", original_name="BV-02.pdf"
    )

    listed = client.get("/api/v1/projects/p1/documents")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [document["id"]]

    detail = client.get(f"/api/v1/projects/p1/documents/{document['id']}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["page_count"] == 2
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert body["pages"][0]["drawing_number"] == "BV-01"

    assert client.get(f"/api/v1/projects/p2/documents/{document['id']}").status_code == 404
    assert client.get(f"/api/v1/projects/p1/documents/{other['id']}").status_code == 404


def test_page_metadata_and_render_are_available_without_ocr_text(client, session_factory):
    document = add_source_document(session_factory, suffix="render", page_rendered=True)

    page = client.get(
        f"/api/v1/projects/p1/documents/{document['id']}/pages/1"
    )
    assert page.status_code == 200, page.text
    body = page.json()
    assert body["page_number"] == 1
    assert body["render_url"].endswith(
        f"/documents/{document['id']}/pages/1/render"
    )
    assert body["drawing_number"] == "BV-01"

    render = client.get(body["render_url"])
    assert render.status_code == 200
    assert render.headers["content-type"] == "image/png"
    assert render.content.startswith(b"\x89PNG")

    missing = client.get(
        f"/api/v1/projects/p1/documents/{document['id']}/pages/99"
    )
    assert missing.status_code == 404
    assert client.get(
        f"/api/v1/projects/p1/documents/{document['id']}/pages/99/render"
    ).status_code == 404


def test_original_download_is_project_scoped(client, session_factory):
    document = add_source_document(session_factory, suffix="original")
    response = client.get(
        f"/api/v1/projects/p1/documents/{document['id']}/original"
    )
    # The seeded path does not exist on disk; the route must not leak it.
    assert response.status_code == 404
    assert client.get(
        f"/api/v1/projects/p2/documents/{document['id']}/original"
    ).status_code == 404


def test_effective_confirmation_and_versions_use_existing_documents(client, session_factory):
    first = add_source_document(session_factory, suffix="same")
    second = add_source_document(
        session_factory,
        suffix="samev2",
        document_id="doc-same-v2",
        document_key="drawing-same",
        version=2,
        effective=False,
        current=False,
    )

    versions = client.get(
        f"/api/v1/projects/p1/documents/{first['id']}/versions"
    )
    assert versions.status_code == 200
    assert {item["version"] for item in versions.json()} == {1, 2}

    confirmed = client.post(
        f"/api/v1/projects/p1/documents/{second['id']}/effective",
        json={"change_note": "Ban hanh thay the"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["is_effective"] is True
    assert confirmed.json()["change_note"] == "Ban hanh thay the"

    old = client.get(f"/api/v1/projects/p1/documents/{first['id']}").json()
    assert old["is_effective"] is False


def test_removed_document_write_routes_are_gone(client, session_factory):
    document = add_source_document(session_factory, suffix="gone")
    assert client.post(
        "/api/v1/projects/p1/documents", files={"file": ("a.pdf", b"%PDF-", "application/pdf")}
    ).status_code in {404, 405}
    assert client.post(
        f"/api/v1/projects/p1/documents/{document['id']}/reingest"
    ).status_code == 404
    assert client.get(
        f"/api/v1/projects/p1/documents/{document['id']}/compare/{document['id']}"
    ).status_code == 404
