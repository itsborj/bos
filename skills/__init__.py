"""Top-level package redirect for skills.
This re-exports the actual implementation located in api/skills.
"""
import pkgutil, os, sys
# Extend the package path to include the implementation directory
_current_dir = os.path.dirname(__file__)
_impl_dir = os.path.abspath(os.path.join(_current_dir, '..', 'api', 'skills'))
if os.path.isdir(_impl_dir):
    __path__.append(_impl_dir)
else:
    raise ImportError('Skills implementation directory not found')
