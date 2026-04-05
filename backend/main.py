from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import config as hydra_config

from .routes.research import router as research_router
from .routes.sessions import router as sessions_router
from .security import verify_api_key_optional
from .session_store import init_session_store


def _cors_origins() -> list[str]:
    raw = os.environ.get("FRONTEND_ORIGINS", "*").strip()
    if not raw or raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    hydra_config.load_dotenv()
    mode = os.environ.get("SESSION_STORE", "").strip().lower()
    if mode in ("memory", "ram"):
        await init_session_store(memory=True)
    else:
        raw = os.environ.get("SESSION_DB_PATH", "data/sessions.db").strip()
        if raw.lower() == ":memory:":
            await init_session_store(path=":memory:")
        else:
            Path(raw).parent.mkdir(parents=True, exist_ok=True)
            await init_session_store(path=raw)
    yield


app = FastAPI(
    title="Research API",
    description=(
        "Stateful research sessions with **multi-agent** turns (router and specialists, optional "
        "auditor), Hydra-scoped memory, direct Q&A, and one-shot "
        "``/v1/research/run`` via ``core``."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_api_key_optional)]
app.include_router(research_router, dependencies=_auth)
app.include_router(sessions_router, dependencies=_auth)


@app.get("/health")
async def health() -> dict[str, str]:
    from .session_store import store as _store

    kind = type(_store).__name__
    return {"status": "ok", "session_store": kind}


def main() -> None:
    import uvicorn

    host = os.environ.get("BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("BACKEND_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
