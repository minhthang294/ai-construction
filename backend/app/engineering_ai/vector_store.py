"""Persistent sqlite-vec storage for Engineering AI chunk embeddings.

One ``vec0`` virtual table is created per ``(project_id, model, dimension)`` in
the same SQLite file; table names are stable SHA-256 derivations.  The JSON
vector in ``DocumentEmbedding`` remains canonical and is used as fallback when
the extension/table is unavailable.

The store is lazy (created on first ingest), not an in-memory/index-per-request
store.  Callers must commit the surrounding transaction.
"""

from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

_PREFIX = "vec_ea_"
_SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class VectorStoreError(RuntimeError):
    pass


def table_name(project_id: str, model: str, dim: int) -> str:
    digest = hashlib.sha256(f"{project_id}|{model}|{dim}".encode("utf-8")).hexdigest()[:24]
    return f"{_PREFIX}{digest}"


def _quote(name: str) -> str:
    if not _SAFE.match(name):
        raise VectorStoreError("unsafe vector table name")
    return f'"{name}"'


def available(db: Session) -> bool:
    try:
        db.execute(text("SELECT vec_version()")).scalar_one()
        return True
    except Exception:  # noqa: BLE001 - extension is optional
        return False


def ensure_table(db: Session, project_id: str, model: str, dim: int) -> Optional[str]:
    if not available(db) or dim < 1:
        return None
    name = table_name(project_id, model, dim)
    try:
        db.execute(
            text(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {_quote(name)} "
                f"USING vec0("
                f"chunk_id TEXT PRIMARY KEY, "
                f"document_id TEXT, "
                f"page_id TEXT, "
                f"embedding float[{int(dim)}]"
                f")"
            )
        )
        return name
    except Exception:  # noqa: BLE001 - fallback to JSON vectors
        return None


def delete_document(db: Session, project_id: str, model: str, dim: int, document_id: str) -> bool:
    name = ensure_table(db, project_id, model, dim)
    if name is None:
        return False
    try:
        db.execute(
            text(f"DELETE FROM {_quote(name)} WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def delete_chunks(
    db: Session,
    project_id: str,
    model: str,
    dim: int,
    chunk_ids: Sequence[str],
) -> bool:
    if not chunk_ids:
        return True
    name = ensure_table(db, project_id, model, dim)
    if name is None:
        return False
    try:
        from sqlalchemy import bindparam

        statement = text(
            f"DELETE FROM {_quote(name)} WHERE chunk_id IN :chunk_ids"
        ).bindparams(bindparam("chunk_ids", expanding=True))
        db.execute(statement, {"chunk_ids": list(chunk_ids)})
        return True
    except Exception:  # noqa: BLE001
        return False


def upsert_vectors(
    db: Session,
    project_id: str,
    model: str,
    dim: int,
    rows: Sequence[Tuple[str, str, str, List[float]]],
) -> bool:
    """Insert/update ``(chunk_id, document_id, page_id, vector)`` rows."""

    if not rows:
        return True
    name = ensure_table(db, project_id, model, dim)
    if name is None:
        return False
    try:
        import sqlite_vec
    except Exception:  # noqa: BLE001
        return False

    for chunk_id, document_id, page_id, vector in rows:
        if len(vector) != dim:
            continue
        payload = sqlite_vec.serialize_float32([float(value) for value in vector])
        try:
            result = db.execute(
                text(
                    f"UPDATE {_quote(name)} "
                    "SET document_id = :document_id, page_id = :page_id, embedding = :embedding "
                    "WHERE chunk_id = :chunk_id"
                ),
                {
                    "document_id": document_id,
                    "page_id": page_id,
                    "embedding": payload,
                    "chunk_id": chunk_id,
                },
            )
            if result.rowcount:
                continue
            db.execute(
                text(
                    f"INSERT INTO {_quote(name)} "
                    "(chunk_id, document_id, page_id, embedding) "
                    "VALUES (:chunk_id, :document_id, :page_id, :embedding)"
                ),
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "page_id": page_id,
                    "embedding": payload,
                },
            )
        except Exception:  # noqa: BLE001 - one bad row must not abort ingest
            return False
    return True


def knn(
    db: Session,
    project_id: str,
    model: str,
    dim: int,
    vector: Sequence[float],
    limit: int,
) -> List[Tuple[str, float]]:
    if not vector or len(vector) != dim or limit < 1:
        return []
    name = ensure_table(db, project_id, model, dim)
    if name is None:
        return []
    try:
        import sqlite_vec

        payload = sqlite_vec.serialize_float32([float(value) for value in vector])
        rows = db.execute(
            text(
                f"SELECT chunk_id, distance FROM {_quote(name)} "
                "WHERE embedding MATCH :embedding "
                "ORDER BY distance LIMIT :limit"
            ),
            {"embedding": payload, "limit": int(limit)},
        ).all()
        return [(str(row[0]), float(row[1])) for row in rows if row[0]]
    except Exception:  # noqa: BLE001
        return []
