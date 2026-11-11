"""Acceptance (PYC/BBNT) module.

The public entry point is :data:`router`.  The module deliberately keeps its own
ORM tables and service layer so it can be tested in isolation; Codex can later
map the Pydantic contracts to shared models or keep these tables.
"""

from .router import router

__all__ = ["router"]
