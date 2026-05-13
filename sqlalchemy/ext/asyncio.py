"""Stub for sqlalchemy.ext.asyncio.AsyncSession used in BOS tests.
Provides a minimal async context manager that mimics the real class.
"""

class AsyncSession:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def execute(self, *args, **kwargs):
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

# Stub async_sessionmaker similar to the one in the top-level sqlalchemy package
def async_sessionmaker(engine, **kwargs):
    from . import DummyAsyncSession

    class _SessionFactory:
        def __call__(self, *a, **kw):
            return DummyAsyncSession()
    return _SessionFactory()

# Stub create_async_engine – simply returns the URL as a placeholder
def create_async_engine(url, **kwargs):
    # Return a dummy engine identifier (just the URL)
    return url
