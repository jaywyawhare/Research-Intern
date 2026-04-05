from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import config as hydra_config

from .routes.research import router as research_router
from .routes.sessions import router as sessions_router
from .security import verify_api_key_optional
from .session_store import init_session_store

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    raw = os.environ.get("FRONTEND_ORIGINS", "*").strip()
    if not raw or raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    hydra_config.load_dotenv()
    mode = os.environ.get("SESSION_STORE", "").strip().lower()
    mongo_uri = os.environ.get("MONGODB_URI", "").strip()

    if not mongo_uri and os.environ.get("MONGODB_URI") is not None:
        logger.warning(
            "MONGODB_URI is set but empty in the environment (often MONGODB_URI= in a local .env). "
            "The API will use the in-memory session store until a non-empty URI is loaded."
        )

    if mongo_uri:
        if mode in ("memory", "ram"):
            logger.warning(
                "MONGODB_URI is set — persisting sessions to MongoDB (ignoring SESSION_STORE=%s).",
                mode or "(empty)",
            )
        db_name = os.environ.get("MONGODB_DB", "ai_researcher").strip() or "ai_researcher"
        coll = os.environ.get("MONGODB_COLLECTION", "research_sessions").strip() or "research_sessions"
        logger.info(
            "Persisting research sessions to MongoDB (db=%s, collection=%s)",
            db_name,
            coll,
        )
        await init_session_store(
            mongo_uri=mongo_uri,
            mongo_db=db_name,
            mongo_collection=coll,
        )
        from .mongo_session_store import MongoSessionStore
        from .session_store import store as _sess

        if isinstance(_sess, MongoSessionStore):
            n = await _sess.count_documents()
            logger.info(
                "MongoDB session collection ready: %s.%s contains %s document(s)",
                db_name,
                coll,
                n,
            )
        logger.info("Active session backend: MongoSessionStore (sessions persist to Atlas)")
    elif mode == "mongodb":
        raise RuntimeError("SESSION_STORE=mongodb requires MONGODB_URI in the environment")
    elif mode in ("memory", "ram"):
        await init_session_store(memory=True)
        logger.info(
            "Active session backend: MemorySessionStore (SESSION_STORE=%s; not using Mongo)",
            mode,
        )
    else:
        logger.warning(
            "MONGODB_URI not set — using in-memory session store (sessions are lost on API restart). "
            "Set MONGODB_URI for MongoDB persistence."
        )
        await init_session_store(memory=True)
        logger.info("Active session backend: MemorySessionStore (MONGODB_URI unset or empty)")
    try:
        yield
    finally:
        from .session_store import store as _sess_store

        closer = getattr(_sess_store, "close", None)
        if callable(closer):
            closer()


app = FastAPI(
    title="AI Researcher API",
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
    from .mongo_session_store import MongoSessionStore
    from .session_store import store as _store

    kind = type(_store).__name__
    out: dict[str, str] = {"status": "ok", "session_store": kind}
    mongo_db = getattr(_store, "db_name", None)
    mongo_coll = getattr(_store, "collection_name", None)
    if isinstance(mongo_db, str) and mongo_db:
        out["mongo_db"] = mongo_db
    if isinstance(mongo_coll, str) and mongo_coll:
        out["mongo_collection"] = mongo_coll
    # Helps debug empty Atlas: if true but store is still MemorySessionStore, something is wrong.
    out["mongodb_uri_in_env"] = "yes" if os.environ.get("MONGODB_URI", "").strip() else "no"
    if isinstance(_store, MongoSessionStore):
        n = await _store.count_documents()
        out["mongo_session_count"] = str(n)
    return out


def main() -> None:
    import uvicorn

    host = os.environ.get("BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("BACKEND_PORT", "8000"))
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
