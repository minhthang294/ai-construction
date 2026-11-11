"""Embedding providers and deterministic local vector indexing.

The default provider is a local signed feature-hashing embedder.  It requires no
key or network and gives stable vectors for the same text, which keeps tests and
offline deployments reproducible.  It is **not** a semantic model: it has no
synonym, paraphrase or cross-language understanding, so retrieval recall still
depends mainly on lexical overlap.  Configure a multilingual/Vietnamese
embedding endpoint for semantic recall.  An OpenAI-compatible embedding endpoint
can be enabled through server-side environment variables.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import List, Optional, Protocol

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

_STOPWORDS = {
    "va", "và", "cua", "của", "cho", "cac", "các", "nhung", "những", "trong",
    "theo", "voi", "với", "la", "là", "co", "có", "duoc", "được", "khong",
    "không", "mot", "một", "tai", "tại", "tu", "từ", "den", "đến", "ve", "về",
    "thi", "thì", "nay", "này", "do", "đó", "de", "để", "khi", "vao", "vào",
    "ra", "tren", "trên", "duoi", "dưới", "giua", "giữa", "the", "and", "or",
    "of", "to", "in", "for", "with", "is", "are", "be", "as", "at", "by",
}


def fold_text(value: str) -> str:
    """Lowercase and strip Vietnamese diacritics for lexical matching."""

    import unicodedata

    text = unicodedata.normalize("NFD", (value or "").lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d")


def tokenize(value: str) -> List[str]:
    return [tok for tok in _TOKEN_RE.findall(fold_text(value)) if tok not in _STOPWORDS]


class EmbeddingProvider(Protocol):
    name: str
    dim: int

    def embed(self, text: str) -> List[float]:
        ...


class HashingEmbeddingProvider:
    """Signed feature hashing over unigrams and bigrams (L2-normalized)."""

    def __init__(self, dim: Optional[int] = None) -> None:
        self.dim = int(dim or os.getenv("ENGINEERING_AI_EMBEDDING_DIM", "256"))
        if self.dim < 32 or self.dim > 4096:
            raise ValueError("embedding dimension must be between 32 and 4096")
        self.name = f"local-hash-v1:{self.dim}"

    def _bucket(self, feature: str) -> tuple[int, float]:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % self.dim
        sign = 1.0 if digest[4] & 1 else -1.0
        return index, sign

    def embed(self, text: str) -> List[float]:
        tokens = tokenize(text)
        vector = [0.0] * self.dim
        for token in tokens:
            index, sign = self._bucket(token)
            vector[index] += sign
        for left, right in zip(tokens, tokens[1:]):
            index, sign = self._bucket(f"{left}_{right}")
            vector[index] += 0.5 * sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm > 0:
            vector = [value / norm for value in vector]
        return vector

    def embed_query(self, text: str) -> List[float]:
        return self.embed(text)


class OpenAICompatibleEmbeddingProvider:
    """Server-side embedding endpoint for multilingual/Vietnamese models.

    The endpoint must accept an OpenAI-style
    ``{"model": ..., "input": text} -> {"data":[{"embedding":[...]}]}`` body
    (common for TEI/vLLM/LM Studio/OpenAI-compatible gateways).  Configure a
    multilingual model such as a Vietnamese-capable E5/BGE model, its true
    dimension, and optional E5-style query/document prefixes.
    """

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str,
        dim: int,
        timeout: float = 60.0,
        query_prefix: str = "",
        document_prefix: str = "",
        request_style: str = "openai",
    ) -> None:
        self.endpoint = endpoint
        self.model = model
        self._api_key = api_key
        self.dim = dim
        self.timeout = timeout
        self.query_prefix = query_prefix
        self.document_prefix = document_prefix
        self.request_style = request_style.strip().lower() or "openai"
        prefix_digest = hashlib.sha256(
            f"{query_prefix}\0{document_prefix}\0{self.request_style}".encode("utf-8")
        ).hexdigest()[:8]
        self.name = f"openai_compatible:{model}:{dim}:{prefix_digest}"

    @staticmethod
    def _extract_vector(data) -> list:
        if isinstance(data, dict):
            candidates = [data.get("embedding"), data.get("vector")]
            if isinstance(data.get("data"), list) and data["data"]:
                item = data["data"][0]
                candidates.append(item.get("embedding") if isinstance(item, dict) else item)
            if isinstance(data.get("embeddings"), list) and data["embeddings"]:
                item = data["embeddings"][0]
                candidates.append(item.get("embedding") if isinstance(item, dict) else item)
            for candidate in candidates:
                if isinstance(candidate, list):
                    return candidate
        if isinstance(data, list):
            if data and isinstance(data[0], list):
                return data[0]
            if data and all(isinstance(item, (int, float)) for item in data):
                return data
        raise RuntimeError("embedding provider returned an unsupported response")

    def _embed(self, text: str, prefix: str) -> List[float]:
        import httpx

        content = f"{prefix}{text}"
        if self.request_style in {"inputs", "hf", "tei"}:
            payload = {"inputs": content}
        else:
            payload = {"model": self.model, "input": content}
        response = httpx.post(
            self.endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        vector = self._extract_vector(response.json())
        if not isinstance(vector, list) or len(vector) != self.dim:
            raise RuntimeError("embedding provider returned unexpected dimension")
        return [float(value) for value in vector]

    def embed(self, text: str) -> List[float]:
        return self._embed(text, self.document_prefix)

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text, self.query_prefix)


def embed_query(provider: EmbeddingProvider, text: str) -> List[float]:
    """Use asymmetric query prefixes when the provider supports them."""

    method = getattr(provider, "embed_query", None)
    if callable(method):
        return method(text)
    return provider.embed(text)


def embeddings_from_env() -> EmbeddingProvider:
    name = (os.getenv("ENGINEERING_AI_EMBEDDING_PROVIDER") or "local").strip().lower()
    if name in {
        "openai",
        "openai_compatible",
        "openai-compatible",
        "multilingual",
        "vietnamese",
    }:
        endpoint = (os.getenv("ENGINEERING_AI_EMBEDDING_URL") or "").strip()
        model = (os.getenv("ENGINEERING_AI_EMBEDDING_MODEL") or "").strip()
        api_key = (
            os.getenv("ENGINEERING_AI_EMBEDDING_API_KEY")
            or os.getenv("ENGINEERING_AI_API_KEY")
            or ""
        ).strip()
        try:
            dim = int(os.getenv("ENGINEERING_AI_EMBEDDING_DIM", "256"))
        except ValueError:
            dim = 256
        if dim < 1:
            dim = 256
        if endpoint and model and api_key:
            return OpenAICompatibleEmbeddingProvider(
                endpoint=endpoint,
                model=model,
                api_key=api_key,
                dim=dim,
                timeout=float(os.getenv("ENGINEERING_AI_TIMEOUT", "60")),
                query_prefix=os.getenv("ENGINEERING_AI_EMBEDDING_QUERY_PREFIX", ""),
                document_prefix=os.getenv("ENGINEERING_AI_EMBEDDING_DOCUMENT_PREFIX", ""),
                request_style=os.getenv("ENGINEERING_AI_EMBEDDING_REQUEST_STYLE", "openai"),
            )
    try:
        return HashingEmbeddingProvider()
    except ValueError:
        return HashingEmbeddingProvider(256)


def cosine(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    lnorm = math.sqrt(sum(a * a for a in left))
    rnorm = math.sqrt(sum(b * b for b in right))
    if lnorm == 0 or rnorm == 0:
        return 0.0
    return dot / (lnorm * rnorm)
