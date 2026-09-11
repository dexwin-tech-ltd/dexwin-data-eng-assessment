import os
from urllib.parse import urlparse

import psycopg2

from pipeline.config import DATABASE_URL


def connect():
    """Open a warehouse connection. Single attempt — no retry."""
    url = os.getenv("DATABASE_URL", DATABASE_URL)
    parsed = urlparse(url)
    return psycopg2.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "dexmart",
        password=parsed.password or "dexmart",
        dbname=(parsed.path or "/warehouse").lstrip("/") or "warehouse",
    )
