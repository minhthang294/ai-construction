"""Engineering AI module: source PDF ingestion, page-grounded retrieval, cited answers.

Mount point for Codex: ``from app.engineering_ai.router import router`` and
include it under ``/api/v1``.  See ``docs/agent-reports/engineering-ai.md``.
"""

from .constants import (
    CROSS_REFERENCE_DISCLAIMER,
    CROSS_REFERENCE_NO_FINDING,
    LOW_OCR_WARNING,
    NO_SOURCE_ANSWER,
    UNVERIFIED_KB_NOTE,
    VISION_DISCLAIMER,
)

__all__ = [
    "router",
    "NO_SOURCE_ANSWER",
    "LOW_OCR_WARNING",
    "UNVERIFIED_KB_NOTE",
    "VISION_DISCLAIMER",
    "CROSS_REFERENCE_DISCLAIMER",
    "CROSS_REFERENCE_NO_FINDING",
]


def __getattr__(name: str):
    if name == "router":
        from .router import router

        return router
    raise AttributeError(name)
