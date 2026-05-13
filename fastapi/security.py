"""Stub security utilities for FastAPI.
Provides a minimal ``APIKeyHeader`` class used for API‑key authentication.
The real FastAPI implementation is much richer, but for unit tests we only need
the constructor signature and a ``__call__`` that returns the header value.
"""

class APIKeyHeader:
    def __init__(self, *, name: str, auto_error: bool = True):
        self.name = name
        self.auto_error = auto_error

    def __call__(self, request):
        # In tests this will never be called; we just provide a placeholder.
        return None
