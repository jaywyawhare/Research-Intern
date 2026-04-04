from __future__ import annotations

import os
from typing import Annotated

from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key_optional(
    x_api_key: str | None = Security(_api_key_header),
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.environ.get("RESEARCH_API_KEY", "").strip()
    if not expected:
        return
    token = (x_api_key or "").strip()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
