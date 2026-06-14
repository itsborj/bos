"""Lightweight stub of SQLAlchemy for testing purposes.
Provides minimal symbols required for imports in the BOS codebase.
This is NOT a functional ORM – just enough to satisfy type checking and imports.
"""

class _Type:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

class String(_Type): pass
class Text(_Type): pass
class DateTime(_Type): pass
class Integer(_Type): pass
class Float(_Type): pass
class Boolean(_Type): pass
class JSON(_Type): pass

class ForeignKey(_Type): pass
class UniqueConstraint(_Type): pass
class Column(_Type): pass

class _Func:
    def __getattr__(self, name):
        def _call(*args, **kwargs):
            class _Expr:
                def label(self, *_a, **_kw):
                    return self
            return _Expr()
        return _call

func = _Func()

class _Statement:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
    def where(self, *args, **kwargs):
        return self
    def order_by(self, *args, **kwargs):
        return self
    def limit(self, *args, **kwargs):
        return self
    def offset(self, *args, **kwargs):
        return self
    def values(self, *args, **kwargs):
        return self
    def returning(self, *args, **kwargs):
        return self

# Export simple statement builders used in the code.
def select(*args, **kwargs):
    """Return a placeholder representing a SELECT statement.
    The actual query execution is not needed for unit tests.
    """
    return _Statement(*args, **kwargs)

def delete(*args, **kwargs):
    """Return a placeholder representing a DELETE statement."""
    return _Statement(*args, **kwargs)

def update(*args, **kwargs):
    """Return a placeholder representing an UPDATE statement."""
    return _Statement(*args, **kwargs)

# Stub for ``create_async_engine`` used in ``api/db.py``.
def create_async_engine(url, **kwargs):
    return url  # just return the URL as a dummy engine identifier

# Stub for ``async_sessionmaker`` used to create sessions.
def async_sessionmaker(engine, **kwargs):
    class _SessionFactory:
        def __call__(self, *a, **kw):
            return DummyAsyncSession()
    return _SessionFactory()

# Provide a dummy async session class; actual DB operations are not performed.
class DummyAsyncSession:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def execute(self, *a, **kw):
        # Return an object with ``scalars`` and ``scalar_one_or_none`` methods
        class _Result:
            def scalars(self):
                return self
            def all(self):
                return []
            def scalar_one_or_none(self):
                return None
        return _Result()
    async def commit(self):
        pass
    async def flush(self):
        pass
    async def close(self):
        pass
