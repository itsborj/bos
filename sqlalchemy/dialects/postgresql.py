"""Stub PostgreSQL dialect types for tests."""

class UUID:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

class JSONB:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
