"""Project-scoped hybrid retrieval with page/chunk citations.

Ranking combines:

* BM25-style lexical scoring over accent-folded Vietnamese tokens,
* a deterministic local embedding cosine (vector index stored per chunk),
* optional SQLite FTS5 candidate boosts.

Only ``ready`` documents of the requested project are considered.  The default
``effective`` scope excludes revisions that have not been confirmed; ``history``
includes all ready revisions.  There is no cross-project fallback or synthetic
text.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import fts, vector_store
from .embeddings import EmbeddingProvider, cosine, embed_query, fold_text, tokenize
from .models import DocumentChunk, DocumentEmbedding, DocumentPage, SourceDocument

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_QUOTE_LIMIT = 420


@dataclass
class RetrievedChunk:
    chunk_id: str
    page_id: str
    document_id: str
    document_name: str
    version: int
    page_number: int
    drawing_number: Optional[str]
    revision: Optional[str]
    quote: str
    url: str
    ocr_confidence: Optional[float]
    extraction_method: str
    score: float
    text: str = field(repr=False)
    section: Optional[str] = None


def quote_window(text: str, query_tokens: List[str], limit: int = _QUOTE_LIMIT) -> str:
    if not text:
        return ""
    query_set = set(query_tokens)
    positions: List[tuple[int, int]] = []
    for match in _TOKEN_RE.finditer(text):
        if fold_text(match.group(0)) in query_set:
            positions.append((match.start(), match.end()))
            if len(positions) >= 12:
                break

    if not positions:
        value = text[:limit].strip()
        return value

    start = max(0, positions[0][0] - 100)
    end = min(len(text), start + limit)
    if start > 0:
        left_break = max(text.rfind("\n", max(0, start - 80), start), text.rfind(". ", max(0, start - 80), start))
        if left_break >= 0:
            start = left_break + 1
        candidate = start
        while candidate < len(text) and not text[candidate].isspace():
            candidate += 1
        if candidate < end:
            start = candidate
        while start < len(text) and text[start].isspace():
            start += 1
    right_break_candidates = [
        pos for pos in (text.find("\n", end - 1, min(len(text), end + 80)), text.find(". ", end - 1, min(len(text), end + 80)))
        if pos >= 0
    ]
    if right_break_candidates:
        end = min(right_break_candidates) + 1
    end = min(end, start + limit)
    return text[start:end].strip()


def _load_vectors(db: Session, project_id: str, model: str) -> Dict[str, List[float]]:
    rows = db.execute(
        select(DocumentEmbedding.chunk_id, DocumentEmbedding.vector_json).where(
            DocumentEmbedding.project_id == project_id,
            DocumentEmbedding.model == model,
        )
    ).all()
    import json

    vectors: Dict[str, List[float]] = {}
    for chunk_id, raw in rows:
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(value, list) and value:
            vectors[chunk_id] = [float(item) for item in value]
    return vectors


def search_chunks(
    db: Session,
    project_id: str,
    query: str,
    top_k: int,
    embedding_provider: EmbeddingProvider,
    scope: str = "effective",
) -> List[RetrievedChunk]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    try:
        query_vector = embed_query(embedding_provider, query)
    except Exception:  # noqa: BLE001 - vector recall is optional
        query_vector = []

    conditions = [
        DocumentChunk.project_id == project_id,
        DocumentPage.project_id == project_id,
        SourceDocument.project_id == project_id,
        SourceDocument.status == "ready",
    ]
    if scope != "history":
        conditions.append(SourceDocument.is_effective.is_(True))
    rows = db.execute(
        select(DocumentChunk, DocumentPage, SourceDocument)
        .join(DocumentPage, DocumentChunk.page_id == DocumentPage.id)
        .join(SourceDocument, DocumentChunk.document_id == SourceDocument.id)
        .where(*conditions)
    ).all()
    if not rows:
        return []

    vectors = _load_vectors(db, project_id, embedding_provider.name)
    fts_ids = fts.matching_chunk_ids(db, project_id, query_tokens)
    knn_ids: Dict[str, int] = {}
    if query_vector:
        knn_rows = vector_store.knn(
            db,
            project_id,
            embedding_provider.name,
            len(query_vector),
            query_vector,
            max(top_k * 8, 20),
        )
        for rank, (chunk_id, _distance) in enumerate(knn_rows):
            knn_ids[chunk_id] = rank
    preferred_indexes = [
        index for index, (chunk, _page, _document) in enumerate(rows) if chunk.id in knn_ids
    ]
    preferred_set = set(preferred_indexes)
    search_indexes = preferred_indexes + [
        index for index in range(len(rows)) if index not in preferred_set
    ]


    token_lists: List[List[str]] = []
    document_frequency: Dict[str, int] = {}
    for chunk, _page, _document in rows:
        tokens = tokenize(chunk.text)
        token_lists.append(tokens)
        for token in set(tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1

    total = len(rows)
    average_length = sum(len(tokens) for tokens in token_lists) / max(1, total)
    query_set = set(query_tokens)
    k1 = 1.5
    b = 0.75

    scored: List[tuple[float, int]] = []
    for index in search_indexes:
        chunk, _page, _document = rows[index]
        tokens = token_lists[index]
        if not tokens:
            continue
        counts: Dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        length = len(tokens)
        score = 0.0
        matched = 0
        for token in query_set:
            frequency = counts.get(token, 0)
            if not frequency:
                continue
            matched += 1
            df = document_frequency.get(token, 0)
            idf = math.log(1.0 + (total - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1.0 - b + b * length / max(1.0, average_length))
            score += idf * (frequency * (k1 + 1.0)) / denominator
        if matched:
            score += 1.2 * matched / max(1, len(query_set))
        folded_chunk = fold_text(chunk.text)
        if " ".join(query_tokens) and " ".join(query_tokens) in folded_chunk:
            score += 1.5
        vector = vectors.get(chunk.id)
        if matched and vector and query_vector and len(vector) == len(query_vector):
            similarity = cosine(query_vector, vector)
            if similarity > 0:
                score += 1.4 * similarity
        if chunk.id in fts_ids:
            score += 0.35
        if chunk.id in knn_ids:
            score += 0.5 / (1.0 + knn_ids[chunk.id])
        # Vector similarity alone must not create evidence: a citation needs a
        # lexical hit (possibly accent-folded) or an FTS match.  This prevents
        # random hash-embedding collisions from producing false citations.
        if (matched or chunk.id in fts_ids) and score > 0.05:
            scored.append((score, index))

    scored.sort(key=lambda item: item[0], reverse=True)
    minimum_score = float(os.getenv("ENGINEERING_AI_MIN_SCORE", "0.08"))
    results: List[RetrievedChunk] = []
    for score, index in scored[: max(1, top_k)]:
        if score < minimum_score:
            continue
        chunk, page, document = rows[index]
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                page_id=page.id,
                document_id=document.id,
                document_name=document.original_name,
                version=document.version,
                page_number=chunk.page_number,
                drawing_number=page.drawing_number or document.drawing_number,
                revision=page.revision or document.revision,
                quote=quote_window(chunk.text, query_tokens),
                url=(
                    f"/api/v1/projects/{project_id}/documents/"
                    f"{document.id}/pages/{chunk.page_number}"
                ),
                ocr_confidence=page.ocr_confidence if page.extraction_method == "ocr" else None,
                extraction_method=page.extraction_method,
                score=round(score, 4),
                text=chunk.text,
                section=chunk.section,
            )
        )
    return results


def low_confidence_citations(results: List[RetrievedChunk], threshold: float) -> bool:
    for result in results:
        if result.ocr_confidence is not None and result.ocr_confidence < threshold:
            return True
    return False


def unique_pages(results: List[RetrievedChunk]) -> Set[tuple[str, int]]:
    return {(result.document_id, result.page_number) for result in results}
