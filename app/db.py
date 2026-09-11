from __future__ import annotations

import os

import psycopg

DEFAULT_URL = "postgresql://lang:lang@localhost:5433/lang_trainer"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url())
