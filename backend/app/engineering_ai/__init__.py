"""Engineering AI module: read-only project sources, page extractions and chat.

Mount point for Codex: ``from app.engineering_ai.router import router`` and
include it under ``/api/v1``.  See ``docs/agent-reports/engineering-ai.md``.
"""

from .constants import LOW_OCR_WARNING, NO_SOURCE_ANSWER, UNVERIFIED_KB_NOTE

__all__ = [
    "router",
    "NO_SOURCE_ANSWER",
    "LOW_OCR_WARNING",
    "UNVERIFIED_KB_NOTE",
]


def __getattr__(name: str):
    if name == "router":
        from .router import router

        return router
    raise AttributeError(name)
