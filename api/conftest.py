"""Pytest path setup for CI and local runs.

GitHub Actions runs tests after `cd api`, while local agent commands may run from
repo root. Some tests import modules as `api.plugins...` to verify package-level
plugin paths. When the working directory is the api package itself, provide a
lightweight `api` package alias that points at this directory.

Do not prepend the repository root to sys.path here: the repo contains a local
`fastapi/` compatibility package used elsewhere, and putting the repo root ahead
of site-packages shadows the real FastAPI dependency during CI tests.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

API_DIR = Path(__file__).resolve().parent

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

if "api" not in sys.modules:
    api_pkg = types.ModuleType("api")
    api_pkg.__path__ = [str(API_DIR)]
    sys.modules["api"] = api_pkg
