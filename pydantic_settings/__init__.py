"""Very small stub of pydantic_settings for the test suite.
Provides a ``BaseSettings`` class that simply inherits from ``pydantic.BaseModel``
and loads values from environment variables with default fall‑backs.
Only the attributes used in ``api/config.py`` are needed.
"""
from pydantic import BaseModel
import os

class BaseSettings(BaseModel):
    class Config:
        env_prefix = ""
        case_sensitive = False

    @classmethod
    def __get_validators__(cls):
        # pydantic expects this for custom types; we provide a no‑op validator.
        yield lambda v: v

    def __init__(self, **data):
        # Load any missing fields from env vars if present.
        env_data = {}
        for field in self.__annotations__:
            env_key = field.upper()
            if env_key in os.environ:
                env_data[field] = os.environ[env_key]
        super().__init__(**{**env_data, **data})
