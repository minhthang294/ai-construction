"""Single database connection and metadata shared by all modules."""

import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


@event.listens_for(Engine, "connect")
def _load_sqlite_extensions(dbapi_connection, _connection_record):
    """Load sqlite-vec on every SQLite connection when available.

    The vector index lives in the same persistent SQLite file as the rest of
    the application. If the optional extension is missing, the application
    falls back to the existing JSON cosine ranker.
    """

    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    try:
        import sqlite_vec

        dbapi_connection.enable_load_extension(True)
        sqlite_vec.load(dbapi_connection)
        dbapi_connection.enable_load_extension(False)
    except Exception:  # noqa: BLE001 - optional capability
        return

_default_db = Path(__file__).resolve().parents[3] / "data" / "app.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db}")
if DATABASE_URL.startswith("sqlite:///") and DATABASE_URL != "sqlite:///:memory:":
    Path(DATABASE_URL[len("sqlite:///"):]).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite:") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db
