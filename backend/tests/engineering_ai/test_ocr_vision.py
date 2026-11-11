from app.engineering_ai.embeddings import HashingEmbeddingProvider
from app.engineering_ai.providers import ExtractiveProvider, provider_from_env


def _fake_png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"fake-image-content" * 5


def test_photo_suggestion_is_proposal_only(client, vision_provider):
    response = client.post(
        "/api/v1/projects/p1/ai/photo-suggestions",
        files=[("file", ("site.png", _fake_png(), "image/png"))],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["requires_confirmation"] is True
    assert body["suggested_category"] == "progress"
    assert body["suggested_caption"] == "Khu vực thi công"
    assert body["disclaimer"]
    assert vision_provider.calls == 1


def test_photo_suggestion_rejects_non_image(client):
    response = client.post(
        "/api/v1/projects/p1/ai/photo-suggestions",
        files=[("file", ("site.txt", b"not an image", "text/plain"))],
    )
    assert response.status_code == 422


def test_photo_suggestion_rejects_oversized_image_before_model_call(
    client, vision_provider, monkeypatch
):
    monkeypatch.setenv("ENGINEERING_AI_MAX_IMAGE_BYTES", "16")
    payload = b"\x89PNG\r\n\x1a\n" + b"x" * 9  # 17 bytes > configured limit
    response = client.post(
        "/api/v1/projects/p1/ai/photo-suggestions",
        files=[("file", ("too-large.png", payload, "image/png"))],
    )
    assert response.status_code == 413, response.text
    assert vision_provider.calls == 0


def test_provider_defaults_to_offline_extractive_without_environment(monkeypatch):
    monkeypatch.delenv("ENGINEERING_AI_PROVIDER", raising=False)
    monkeypatch.delenv("ENGINEERING_AI_API_KEY", raising=False)
    assert isinstance(provider_from_env(), ExtractiveProvider)

    monkeypatch.setenv("ENGINEERING_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("ENGINEERING_AI_CHAT_URL", "https://example.invalid/v1/chat/completions")
    monkeypatch.setenv("ENGINEERING_AI_MODEL", "example-model")
    monkeypatch.delenv("ENGINEERING_AI_API_KEY", raising=False)
    # Missing server-side key must not crash and must not enable an external call.
    assert isinstance(provider_from_env(), ExtractiveProvider)


def test_local_embedding_is_deterministic_and_normalized():
    provider = HashingEmbeddingProvider(64)
    first = provider.embed("concrete cover abutment")
    second = provider.embed("concrete cover abutment")
    assert first == second
    assert len(first) == 64
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6
    assert first != provider.embed("asbestos roof")


def test_ai_routes_are_rate_limited_per_project_user(client, monkeypatch):
    from app.engineering_ai.rate_limit import reset_rate_limits

    reset_rate_limits()
    monkeypatch.setenv("ENGINEERING_AI_RATE_LIMIT_PER_MINUTE", "1")
    first = client.post(
        "/api/v1/projects/rate-project/ai/search",
        json={"query": "concrete"},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/projects/rate-project/ai/search",
        json={"query": "concrete"},
    )
    assert second.status_code == 429
    assert second.headers.get("retry-after")
