"""
dbservice_client

Primary entrypoint:
  - Session(...)

Exceptions:
  - DbServiceError
  - DbServiceConnectionError
  - DbServiceClosedError
"""

from .session import Session
from .errors import (
    DbServiceError,
    DbServiceConnectionError,
    DbServiceClosedError,
)

__all__ = [
    "Session",
    "DbServiceError",
    "DbServiceConnectionError",
    "DbServiceClosedError",
]
