"""Package redirect for providers.
Allows imports like `from providers.connector_registry import ...` to resolve to `api/providers`.
"""
import os
_impl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'api', 'providers'))
if os.path.isdir(_impl_dir):
    __path__.append(_impl_dir)
else:
    raise ImportError('Providers implementation directory not found')
