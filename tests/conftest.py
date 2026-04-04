from __future__ import annotations

import os

# Before importing the FastAPI app so lifespan picks the in-memory session backend.
os.environ.setdefault("SESSION_STORE", "memory")

import pytest
from starlette.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c
