"""Module-local error type used to produce the v1 ``{detail, code}`` shape."""

from __future__ import annotations


class AcceptanceError(Exception):
    """A deterministic acceptance error with an HTTP status and stable code."""

    def __init__(self, status_code: int, detail: str, code: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class TemplateError(AcceptanceError):
    """Raised when the configured PYC/BBNT workbook cannot be used."""

    def __init__(self, detail: str, code: str = "template_invalid") -> None:
        super().__init__(500, detail, code)
