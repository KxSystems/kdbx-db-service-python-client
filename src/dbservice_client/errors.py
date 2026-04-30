from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class DbServiceConnectionError(RuntimeError):
    """Raised when a network connection cannot be established."""


class DbServiceClosedError(RuntimeError):
    """Raised when attempting to use a closed session."""


@dataclass
class DbServiceError(RuntimeError):
    """Represents an error response from the service."""
    message: str
    status_code: Optional[int] = None
    payload: Any = None
    method: Optional[str] = None
    path: Optional[str] = None
    api: Optional[str] = None
    code: Optional[str] = None
    title: Optional[str] = None
    error_message: Optional[str] = None
    detail: Optional[str] = None
    retryable: Optional[bool] = None
    corr_id: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)
        self._parse_payload()

    def _parse_payload(self) -> None:
        if not isinstance(self.payload, dict):
            if isinstance(self.payload, str) and not self.error_message:
                self.error_message = self.payload
            return

        # New envelope: {errors: [...], meta: {...}}
        errors = self.payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                if self.code is None:
                    self.code = first.get("code")
                if self.title is None:
                    self.title = first.get("title")
                if self.detail is None:
                    self.detail = first.get("detail")
                if self.retryable is None:
                    self.retryable = first.get("retryable")
                if self.error_message is None:
                    self.error_message = first.get("message") or first.get("title") or first.get("detail")

        meta = self.payload.get("meta")
        if isinstance(meta, dict):
            if self.corr_id is None:
                self.corr_id = meta.get("corrId")
            if self.updated_at is None:
                self.updated_at = meta.get("updatedAt")

        # Legacy: {"error": "..."}
        if self.error_message is None:
            legacy_error = self.payload.get("error")
            if isinstance(legacy_error, str) and legacy_error:
                self.error_message = legacy_error

        # Legacy gateway header format: {"header": {"ai": "..."}}
        if self.error_message is None:
            header = self.payload.get("header")
            if isinstance(header, dict):
                ai = header.get("ai")
                if isinstance(ai, str) and ai:
                    self.error_message = ai

    def __str__(self) -> str:
        ctx_parts = []
        if self.method and self.path:
            ctx_parts.append(f"{self.method.upper()} {self.path}")
        elif self.path:
            ctx_parts.append(self.path)
        if self.api:
            ctx_parts.append(f"api={self.api}")
        ctx = " | ".join(ctx_parts)

        base = self.error_message or self.detail or self.title or self.message
        if self.status_code is not None:
            base = f"{self.status_code} {base}"
        if ctx:
            return f"{base} ({ctx})"
        return base
