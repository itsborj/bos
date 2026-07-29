"""Lightweight stub of FastAPI for testing.
Provides minimal classes/functions used in the codebase to avoid pulling the real FastAPI dependency.
"""

class APIRouter:
    def __init__(self, *args, **kwargs):
        pass
    def get(self, path: str, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def post(self, path: str, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def put(self, path: str, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def patch(self, path: str, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def delete(self, path: str, *args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def include_router(self, router, *args, **kwargs):
        pass
    def add_api_route(self, *args, **kwargs):
        pass

def Depends(dep=None):
    return dep

def Query(default=None, *args, **kwargs):
    return default

def Path(default=None, *args, **kwargs):
    return default

def Body(default=None, *args, **kwargs):
    return default

def File(default=None, *args, **kwargs):
    return default

def Form(default=None, *args, **kwargs):
    return default

class UploadFile:
    def __init__(self, filename: str | None = None, content_type: str | None = None, file=None):
        self.filename = filename
        self.content_type = content_type
        self.file = file
    async def read(self):
        if self.file and hasattr(self.file, 'read'):
            return self.file.read()
        return b''

def Security(dep=None):
    # In real FastAPI this returns a Depends with a security scheme.
    return Depends(dep)
    # NOTE: the line below was unreachable dead code — removed.

class Request:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

class HTTPException(Exception):
    def __init__(self, status_code: int = 500, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
