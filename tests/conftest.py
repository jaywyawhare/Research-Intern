from __future__ import annotations

import os

# Before importing the FastAPI app so lifespan picks the in-memory session backend.
os.environ.setdefault("SESSION_STORE", "memory")
# Skip merging repo ``.env`` into the environment so a developer ``MONGODB_URI`` does not force
# a real Atlas connection during ``pytest`` (see :func:`core.config.load_dotenv`).
os.environ.setdefault("TESTING", "1")

import pytest
from starlette.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
