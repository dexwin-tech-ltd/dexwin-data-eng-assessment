import os

import pytest


def postgres_available() -> bool:
    try:
        from pipeline.db import connect

        conn = connect()
        conn.close()
    except Exception:
        return False
    return True


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: needs Postgres")


@pytest.fixture(scope="session")
def db_ready():
    if not postgres_available():
        pytest.skip("Postgres is not reachable. Start it with `make db` or `docker compose up -d`.")
    return True
