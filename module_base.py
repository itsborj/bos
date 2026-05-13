"""Redirect module for ModuleBase.
Exports the actual implementation from api/module_base.py.
"""
import importlib

# Load the actual implementation module
_real = importlib.import_module('api.module_base')

# Re-export public attributes for compatibility
for _name in dir(_real):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_real, _name)
# Explicitly expose internal helper needed for tests
_get_env = getattr(_real, '_get_env')

# Export any other required symbols (e.g., ModuleBase) via __all__
__all__ = [name for name in globals() if not name.startswith('_')]

