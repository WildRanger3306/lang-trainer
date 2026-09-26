"""Shared switches for tests that need a database."""

from __future__ import annotations

import os
import unittest
from urllib.parse import urlsplit

from app.db import database_url


def database_name() -> str:
    return urlsplit(database_url()).path.lstrip("/")


def db_tests_enabled() -> bool:
    """DB tests run only on a database named *_test (see scripts/test_db.py)."""
    return os.environ.get("RUN_DB_TESTS") == "1" and database_name().endswith("_test")


requires_test_db = unittest.skipUnless(
    db_tests_enabled(),
    "DB tests need RUN_DB_TESTS=1 and a *_test database: python scripts/test_db.py test",
)
