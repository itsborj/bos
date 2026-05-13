"""Redirect package for routers.
Provides access to the implementation under api/routers.
"""
import os
_impl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'api', 'routers'))
if os.path.isdir(_impl_dir):
    __path__.append(_impl_dir)
else:
    raise ImportError('Routers implementation directory not found')
