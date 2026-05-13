"""Redirect package for modules.
Provides access to implementation under api/modules.
"""
import os
_impl_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'api', 'modules'))
if os.path.isdir(_impl_dir):
    __path__.append(_impl_dir)
else:
    raise ImportError('Modules implementation directory not found')
