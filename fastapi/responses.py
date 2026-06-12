"""Stub responses module for FastAPI.
Provides minimal response classes used in the codebase so that
``from fastapi.responses import RedirectResponse, JSONResponse, ...``
does not raise ModuleNotFoundError when this stub directory shadows
the real fastapi package (e.g. during test runs from the project root).
"""


class Response:
    def __init__(self, content=None, status_code: int = 200, headers=None, media_type=None):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.media_type = media_type


class JSONResponse(Response):
    media_type = "application/json"

    def __init__(self, content=None, status_code: int = 200, headers=None):
        super().__init__(content, status_code, headers, "application/json")


class HTMLResponse(Response):
    media_type = "text/html"

    def __init__(self, content=None, status_code: int = 200, headers=None):
        super().__init__(content, status_code, headers, "text/html")


class RedirectResponse(Response):
    def __init__(self, url: str, status_code: int = 307, headers=None):
        super().__init__(None, status_code, headers)
        self.url = url


class StreamingResponse(Response):
    def __init__(self, content=None, status_code: int = 200, headers=None, media_type=None):
        super().__init__(content, status_code, headers, media_type)


class FileResponse(Response):
    def __init__(self, path: str, status_code: int = 200, headers=None, media_type=None, filename=None):
        super().__init__(None, status_code, headers, media_type)
        self.path = path
        self.filename = filename


class PlainTextResponse(Response):
    media_type = "text/plain"

    def __init__(self, content=None, status_code: int = 200, headers=None):
        super().__init__(content, status_code, headers, "text/plain")
