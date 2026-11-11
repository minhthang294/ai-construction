"""SQLite FTS5 index maintenance and document-scoped cleanup.

FTS5 is optional.  Retrieval still works through the lexical/vector ranker when
the SQLite build lacks FTS5; this module only adds candidate recall.
"""

from __future__ import annotations

from typing import Iterable, Set

from sqlalchemy import text
from sqlalchemy.orm import Session

FTS_TABLE = "engineering_ai_chunks_fts"
_FTS_CREATED: set[int] = set()


class FtsUnavailable(RuntimeError):
    pass


def ensure_fts(db: Session) -> bool:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "sqlite":
        return False
    try:
        db.execute(
            text(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
                USING fts5(
                    chunk_id UNINDEXED,
                    project_id UNINDEXED,
                    document_id UNINDEXED,
                    page_number UNINDEXED,
                    text,
                    tokenize='unicode61 remove_diacritics 2'
                )
                """
            )
        )
        return True
    except Exception:  # noqa: BLE001 - optional capability
        return False


def delete_document_rows(db: Session, document_id: str) -> None:
    try:
        db.execute(
            text(f"DELETE FROM {FTS_TABLE} WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
    except Exception:  # noqa: BLE001 - table absent / FTS unavailable
        return


def insert_chunks(db: Session, rows: Iterable[dict]) -> None:
    payload = list(rows)
    if not payload:
        return
    try:
        db.execute(
            text(
                f"INSERT INTO {FTS_TABLE} "
                "(chunk_id, project_id, document_id, page_number, text) "
                "VALUES (:chunk_id, :project_id, :document_id, :page_number, :text)"
            ),
            payload,
        )
    except Exception:  # noqa: BLE001 - optional capability
        return


def _escape_match_token(token: str) -> str:
    return '"' + token.replace('"', '""') + '"'


def matching_chunk_ids(db: Session, project_id: str, tokens: list[str]) -> Set[str]:
    if not tokens:
        return set()
    expression = " OR ".join(_escape_match_token(token) for token in tokens[:24])
    try:
        rows = db.execute(
            text(
                f"SELECT chunk_id FROM {FTS_TABLE} "
                f"WHERE {FTS_TABLE} MATCH :expression AND project_id = :project_id"
            ),
            {"expression": expression, "project_id": project_id},
        ).all()
    except Exception:  # noqa: BLE001 - table absent / unsupported syntax
        return set()
    return {row[0] for row in rows if row[0]}
