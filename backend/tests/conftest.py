"""Access to the real database when one is available (the CI Postgres).

Every test in this suite mocked the session. That is fast, and it is why an
endpoint could ship a 500 to production while the suite was green: no real
`Decimal`, `datetime` or renamed column ever went through the code. These
fixtures give the few tests that need it an actual database, and skip cleanly
when there is none (a laptop with no Postgres).
"""
import os

import pytest


@pytest.fixture(scope="session")
def db_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("no DATABASE_URL: real-database tests are skipped")
    return url


@pytest.fixture
def db(db_url):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"database unreachable: {exc}")

    session = sessionmaker(bind=engine, future=True)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
