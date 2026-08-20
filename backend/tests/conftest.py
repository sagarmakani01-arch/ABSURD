"""Test isolation: route every test against a throwaway SQLite file.

The env var must be set before `app.config` is imported anywhere, so this
module sets it at import time (pytest imports conftest first).
"""

from __future__ import annotations

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="absurd-tests-")
os.environ["ABSURD_DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP_DIR, "test.db").replace("\\", "/")

import pytest  # noqa: E402

from app.db import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    """Fresh schema per test — SQLite drop/create is cheap."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield