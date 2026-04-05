from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any

import certifi

logger = logging.getLogger(__name__)

from .session_store import (
    AbstractSessionStore,
    ResearchSessionRecord,
    SessionStatus,
    _UNSET,
    _copy_rec,
)

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ModuleNotFoundError as e:  # pragma: no cover
    raise ModuleNotFoundError(
        "MongoDB session storage requires motor. Install with: pip install motor"
    ) from e


def _motor_client_kwargs() -> dict[str, Any]:
    """
    TLS options for MongoDB Atlas. Using certifi's CA bundle avoids ``SSL: TLSV1_ALERT_INTERNAL_ERROR``
    on many Linux/Python 3.12+ setups where the default store does not match Atlas.
    """
    kw: dict[str, Any] = {"tlsCAFile": certifi.where()}
    ms = os.environ.get("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "").strip()
    if ms.isdigit():
        kw["serverSelectionTimeoutMS"] = int(ms)
    if os.environ.get("MONGODB_TLS_DISABLE_OCSP", "").strip().lower() in ("1", "true", "yes"):
        kw["tlsDisableOCSPEndpointCheck"] = True
    return kw


class MongoSessionStore(AbstractSessionStore):
    """Persists research sessions in a MongoDB collection."""

    def __init__(self, uri: str, db_name: str, collection_name: str = "research_sessions") -> None:
        self._uri = uri
        self.db_name = db_name
        self.collection_name = collection_name
        self._client = AsyncIOMotorClient(uri, **_motor_client_kwargs())
        self._coll = self._client[db_name][collection_name]
        self._lock = asyncio.Lock()

    async def init_indexes(self) -> None:
        await self._coll.create_index("session_id", unique=True)
        await self._coll.create_index([("created_at", -1)])

    async def count_documents(self) -> int:
        return int(await self._coll.count_documents({}))

    def close(self) -> None:
        self._client.close()

    def new_session_id(self) -> str:
        return f"sess_{uuid.uuid4().hex[:20]}"

    @staticmethod
    def _doc_to_rec(doc: dict[str, Any]) -> ResearchSessionRecord:
        return ResearchSessionRecord(
            session_id=doc["session_id"],
            topic=doc["topic"],
            status=doc["status"],
            created_at=float(doc["created_at"]),
            updated_at=float(doc["updated_at"]),
            use_hydra=bool(doc.get("use_hydra", False)),
            hydra_connected=bool(doc.get("hydra_connected", False)),
            error=doc.get("error"),
            outcome=dict(doc["outcome"]) if isinstance(doc.get("outcome"), dict) else None,
            transcript=list(doc.get("transcript") or []),
        )

    async def create(self, topic: str, *, use_hydra: bool) -> ResearchSessionRecord:
        now = time.time()
        sid = self.new_session_id()
        doc: dict[str, Any] = {
            "session_id": sid,
            "topic": topic.strip(),
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "use_hydra": use_hydra,
            "hydra_connected": False,
            "error": None,
            "outcome": None,
            "transcript": [],
        }
        async with self._lock:
            await self._coll.insert_one(doc)
        logger.info(
            "MongoDB session inserted: session_id=%s topic=%r use_hydra=%s",
            sid,
            topic.strip()[:200],
            use_hydra,
        )
        return ResearchSessionRecord(
            session_id=sid,
            topic=topic.strip(),
            status="pending",
            created_at=now,
            updated_at=now,
            use_hydra=use_hydra,
        )

    async def get(self, session_id: str) -> ResearchSessionRecord | None:
        async with self._lock:
            doc = await self._coll.find_one({"session_id": session_id})
        if not doc:
            return None
        rec = self._doc_to_rec(doc)
        return _copy_rec(rec)

    async def list_summaries(self) -> list[ResearchSessionRecord]:
        async with self._lock:
            cursor = self._coll.find().sort("created_at", -1)
            docs = await cursor.to_list(length=None)
        return [_copy_rec(self._doc_to_rec(d)) for d in docs]

    async def patch(
        self,
        session_id: str,
        *,
        status: SessionStatus | None = None,
        error: Any = _UNSET,
        outcome: Any = _UNSET,
        hydra_connected: bool | None = None,
    ) -> None:
        async with self._lock:
            doc = await self._coll.find_one({"session_id": session_id})
            if not doc:
                return
            rec = self._doc_to_rec(doc)
            if status is not None:
                rec.status = status
            if error is not _UNSET:
                rec.error = error
            if outcome is not _UNSET:
                rec.outcome = outcome
            if hydra_connected is not None:
                rec.hydra_connected = hydra_connected
            rec.updated_at = time.time()
            await self._coll.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "status": rec.status,
                        "updated_at": rec.updated_at,
                        "error": rec.error,
                        "outcome": rec.outcome,
                        "hydra_connected": rec.hydra_connected,
                    }
                },
            )
            if outcome is not _UNSET:
                logger.info(
                    "MongoDB session outcome written: session_id=%s status=%s",
                    session_id,
                    rec.status,
                )
            elif status is not None:
                logger.info(
                    "MongoDB session updated: session_id=%s status=%s",
                    session_id,
                    status,
                )

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            res = await self._coll.delete_one({"session_id": session_id})
        return res.deleted_count > 0

    async def append_transcript(self, session_id: str, entry: dict[str, Any]) -> bool:
        async with self._lock:
            res = await self._coll.update_one(
                {"session_id": session_id},
                {"$push": {"transcript": entry}, "$set": {"updated_at": time.time()}},
            )
        return res.matched_count > 0
