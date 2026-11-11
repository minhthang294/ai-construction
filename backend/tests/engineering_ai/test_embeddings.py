import httpx

from app.engineering_ai.embeddings import (
    HashingEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    embed_query,
    embeddings_from_env,
)


class _FakeResponse:
    def __init__(self, vector):
        self._vector = vector

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"embedding": self._vector}]}


def test_configured_multilingual_embedding_api_uses_query_and_document_prefixes(monkeypatch):
    captured = []

    def fake_post(url, json, headers, timeout):
        captured.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _FakeResponse([0.1, 0.2, 0.3, 0.4])

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_PROVIDER", "vietnamese")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_URL", "https://embed.example/v1/embeddings")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_MODEL", "multilingual-e5-large")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_API_KEY", "embed-secret")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_DIM", "4")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_QUERY_PREFIX", "query: ")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_DOCUMENT_PREFIX", "passage: ")

    provider = embeddings_from_env()
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.name.startswith("openai_compatible:multilingual-e5-large:4:")

    document_vector = provider.embed("lớp bê tông bảo vệ")
    query_vector = embed_query(provider, "chiều dày lớp bảo vệ")

    assert document_vector == [0.1, 0.2, 0.3, 0.4]
    assert query_vector == [0.1, 0.2, 0.3, 0.4]
    assert captured[0]["url"] == "https://embed.example/v1/embeddings"
    assert captured[0]["json"]["model"] == "multilingual-e5-large"
    assert captured[0]["json"]["input"] == "passage: lớp bê tông bảo vệ"
    assert captured[1]["json"]["input"] == "query: chiều dày lớp bảo vệ"
    assert captured[0]["headers"]["Authorization"] == "Bearer embed-secret"


def test_embedding_provider_supports_inputs_style_vietnamese_gateway(monkeypatch):
    captured = {}

    class _InputsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[0.5, 0.5]]}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _InputsResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_PROVIDER", "multilingual")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_URL", "https://tei.example/embed")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_MODEL", "vietnamese-bi-encoder")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_API_KEY", "embed-secret")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_DIM", "2")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_REQUEST_STYLE", "inputs")

    provider = embeddings_from_env()
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.embed("lớp bảo vệ") == [0.5, 0.5]
    assert captured["json"] == {"inputs": "lớp bảo vệ"}
    assert captured["url"] == "https://tei.example/embed"


def test_embedding_provider_falls_back_to_local_hash_without_key(monkeypatch):
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_PROVIDER", "multilingual")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_URL", "https://embed.example/v1/embeddings")
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_MODEL", "multilingual-e5-large")
    monkeypatch.delenv("ENGINEERING_AI_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("ENGINEERING_AI_API_KEY", raising=False)
    monkeypatch.setenv("ENGINEERING_AI_EMBEDDING_DIM", "64")

    provider = embeddings_from_env()
    assert isinstance(provider, HashingEmbeddingProvider)
    assert provider.name == "local-hash-v1:64"


def test_hash_provider_supports_query_embedding_without_asymmetry():
    provider = HashingEmbeddingProvider(64)
    assert embed_query(provider, "concrete cover") == provider.embed("concrete cover")
