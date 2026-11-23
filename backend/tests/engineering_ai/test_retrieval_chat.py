from .conftest import add_page_extraction, cover_extraction


def _post_chat(client, message, **extra):
    return client.post(
        "/api/v1/projects/p1/ai/chat", json={"message": message, **extra}
    )


def _seed_cover_extraction(client, session_factory, digital_document, value="50"):
    pages = client.get(
        f"/api/v1/projects/p1/documents/{digital_document['id']}"
    ).json()["pages"]
    page = next(item for item in pages if item["page_number"] == 2)
    add_page_extraction(
        session_factory,
        project_id="p1",
        document_id=digital_document["id"],
        page_id=page["id"],
        page_number=2,
        extraction=cover_extraction(value),
    )


def test_chat_no_source_uses_exact_refusal_and_persists_conversation(client):
    response = _post_chat(client, "Chiều dày lớp bê tông bảo vệ là bao nhiêu?")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["no_source"] is True
    assert body["confidence"] == 0.0
    assert body["citations"] == []
    assert body["answer"] == "Không tìm thấy thông tin này trong hồ sơ công trình hiện có."
    assert any("chưa được kiểm chứng" in warning for warning in body["warnings"])

    conversation = client.get(
        f"/api/v1/projects/p1/ai/conversations/{body['conversation_id']}"
    )
    assert conversation.status_code == 200, conversation.text
    messages = conversation.json()["messages"]
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == body["answer"]


def test_chat_answers_from_ai_extracted_page_data(
    client, digital_document, answer_provider, session_factory
):
    _seed_cover_extraction(client, session_factory, digital_document)
    answer_provider.response = "Thông tin tại [1] cho biết lớp bảo vệ bê tông là 50 mm."
    body = _post_chat(client, "concrete cover abutment").json()
    assert body["no_source"] is False
    assert body["answer"] == answer_provider.response
    assert len(body["citations"]) == 1
    assert body["confidence"] > 0
    assert answer_provider.calls
    citation = body["citations"][0]
    assert citation["document_id"] == digital_document["id"]
    assert citation["page_number"] == 2
    assert citation["source"] == "page_extraction"
    assert citation["record_id"]
    assert "50 mm" in citation["quote"]

    from sqlalchemy import select

    from app.engineering_ai.models import AICitation

    with session_factory() as db:
        rows = db.scalars(select(AICitation)).all()
    assert len(rows) == 1
    assert rows[0].page_number == citation["page_number"]
    assert rows[0].quote == citation["quote"]


def test_uncited_provider_answer_is_replaced_with_extracted_data(
    client, digital_document, answer_provider, session_factory
):
    _seed_cover_extraction(client, session_factory, digital_document)
    answer_provider.response = "Kết luận không có nguồn."
    body = _post_chat(client, "concrete cover abutment").json()
    assert "Kết luận không có nguồn." not in body["answer"]
    assert "Dữ kiện AI trích xuất" in body["answer"]
    assert any("thiếu citation" in warning for warning in body["warnings"])
    assert body["citations"]


def test_provider_invented_dimension_is_replaced_with_extracted_citation(
    client, digital_document, answer_provider, session_factory
):
    from app.engineering_ai.constants import GROUNDING_WARNING

    _seed_cover_extraction(client, session_factory, digital_document)
    answer_provider.response = "Lớp bảo vệ bê tông là 75 mm [1]."
    body = _post_chat(client, "concrete cover abutment").json()
    assert body["no_source"] is False
    assert "75 mm" not in body["answer"]
    assert "Dữ kiện AI trích xuất" in body["answer"]
    assert GROUNDING_WARNING in body["warnings"]
    assert body["citations"]
    assert any("50 mm" in citation["quote"] for citation in body["citations"])


def test_provider_valid_dimension_present_in_cited_quote_is_retained(
    client, digital_document, answer_provider, session_factory
):
    from app.engineering_ai.constants import GROUNDING_WARNING

    _seed_cover_extraction(client, session_factory, digital_document)
    answer_provider.response = "Lớp bảo vệ bê tông là 50 mm [1]."
    body = _post_chat(client, "concrete cover abutment").json()
    assert body["answer"] == answer_provider.response
    assert GROUNDING_WARNING not in body["warnings"]
    assert body["citations"]
    assert any("50 mm" in citation["quote"] for citation in body["citations"])


def test_chat_without_provider_uses_extracted_data(
    client, digital_document, session_factory
):
    _seed_cover_extraction(client, session_factory, digital_document)
    body = _post_chat(client, "concrete cover abutment").json()
    assert body["no_source"] is False
    assert body["citations"]
    assert "concrete cover for abutment: 50 mm" in body["answer"]


def test_conversation_cannot_cross_projects(client, digital_document):
    created = _post_chat(client, "concrete cover abutment").json()
    cross = client.post(
        "/api/v1/projects/p2/ai/chat",
        json={
            "message": "concrete cover abutment",
            "conversation_id": created["conversation_id"],
        },
    )
    assert cross.status_code == 404

    fetched = client.get(
        f"/api/v1/projects/p2/ai/conversations/{created['conversation_id']}"
    )
    assert fetched.status_code == 404


def test_conversation_create_search_rename_delete(
    client, digital_document, session_factory
):
    _seed_cover_extraction(client, session_factory, digital_document)
    created = client.post(
        "/api/v1/projects/p1/ai/conversations",
        json={"title": "Hoi ve be tong"},
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]

    answer = client.post(
        "/api/v1/projects/p1/ai/chat",
        json={
            "message": "concrete cover abutment",
            "conversation_id": conversation_id,
        },
    )
    assert answer.status_code == 200, answer.text
    assert answer.json()["citations"]

    found = client.get("/api/v1/projects/p1/ai/conversations", params={"q": "be tong"})
    assert found.status_code == 200
    assert [item["id"] for item in found.json()] == [conversation_id]

    missing = client.get("/api/v1/projects/p1/ai/conversations", params={"q": "khong-co"})
    assert missing.json() == []

    renamed = client.patch(
        f"/api/v1/projects/p1/ai/conversations/{conversation_id}",
        json={"title": "Ten moi"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "Ten moi"
    assert renamed.json()["messages"]

    cross = client.patch(
        f"/api/v1/projects/p2/ai/conversations/{conversation_id}",
        json={"title": "Sai project"},
    )
    assert cross.status_code == 404
    assert client.delete(
        f"/api/v1/projects/p2/ai/conversations/{conversation_id}"
    ).status_code == 404

    deleted = client.delete(
        f"/api/v1/projects/p1/ai/conversations/{conversation_id}"
    )
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/projects/p1/ai/conversations/{conversation_id}"
    ).status_code == 404
    assert client.get("/api/v1/projects/p1/ai/conversations").json() == []


def test_removed_ai_routes_are_gone(client):
    for path in (
        "/api/v1/projects/p1/ai/search",
        "/api/v1/projects/p1/ai/cross-references",
        "/api/v1/projects/p1/ai/inspection-checklists",
        "/api/v1/projects/p1/ai/daily-report-drafts",
        "/api/v1/projects/p1/ai/photo-suggestions",
    ):
        assert client.post(path, json={}).status_code == 404
