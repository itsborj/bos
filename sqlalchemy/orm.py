"""Stub ORM module for SQLAlchemy.
Provides a minimal ``DeclarativeBase`` class used by the BOS codebase.
This is sufficient for type checking and import resolution in tests.
"""

class DeclarativeBase:
    """Base class placeholder for declarative ORM models.
    Real SQLAlchemy adds metadata handling; here we only need an empty class.
    """
    pass
