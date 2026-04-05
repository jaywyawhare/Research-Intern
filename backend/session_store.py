from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

SessionStatus = Literal["pending", "running", "ready", "error"]

_UNSET: Any = object()


@dataclass
class ResearchSessionRecord:
    session_id: str
    topic: str
    status: SessionStatus
    created_at: float
    updated_at: float
    use_hydra: bool
    hydra_connected: bool = False
    error: str | None = None
    outcome: dict[str, Any] | None = None
    transcript: list[dict[str, Any]] = field(default_factory=list)


class AbstractSessionStore(ABC):
    @abstractmethod
    def new_session_id(self) -> str: ...

    @abstractmethod
    async def create(self, topic: str, *, use_hydra: bool) -> ResearchSessionRecord: ...

    @abstractmethod
    async def get(self, session_id: str) -> ResearchSessionRecord | None: ...

    @abstractmethod
    async def list_summaries(self) -> list[ResearchSessionRecord]: ...

    @abstractmethod
    async def patch(
        self,
        session_id: str,
        *,
        status: SessionStatus | None = None,
        error: Any = _UNSET,
        outcome: Any = _UNSET,
        hydra_connected: bool | None = None,
    ) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> bool: ...

    @abstractmethod
    async def append_transcript(self, session_id: str, entry: dict[str, Any]) -> bool: ...


@dataclass
class MemorySessionStore(AbstractSessionStore):
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _by_id: dict[str, ResearchSessionRecord] = field(default_factory=dict)

    def new_session_id(self) -> str:
        return f"sess_{uuid.uuid4().hex[:20]}"

    async def create(self, topic: str, *, use_hydra: bool) -> ResearchSessionRecord:
        now = time.time()
        sid = self.new_session_id()
        rec = ResearchSessionRecord(
            session_id=sid,
            topic=topic.strip(),
            status="pending",
            created_at=now,
            updated_at=now,
            use_hydra=use_hydra,
        )
        async with self._lock:
            self._by_id[sid] = rec
        return rec

    async def get(self, session_id: str) -> ResearchSessionRecord | None:
        async with self._lock:
            r = self._by_id.get(session_id)
            return _copy_rec(r) if r else None

    async def list_summaries(self) -> list[ResearchSessionRecord]:
        async with self._lock:
            rows = sorted(self._by_id.values(), key=lambda r: r.created_at, reverse=True)
            return [_copy_rec(r) for r in rows]

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
            rec = self._by_id.get(session_id)
            if rec is None:
                return
            if status is not None:
                rec.status = status
            if error is not _UNSET:
                rec.error = error
            if outcome is not _UNSET:
                rec.outcome = outcome
            if hydra_connected is not None:
                rec.hydra_connected = hydra_connected
            rec.updated_at = time.time()

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            if session_id in self._by_id:
                del self._by_id[session_id]
                return True
            return False

    async def append_transcript(self, session_id: str, entry: dict[str, Any]) -> bool:
        async with self._lock:
            rec = self._by_id.get(session_id)
            if rec is None:
                return False
            rec.transcript.append(entry)
            rec.updated_at = time.time()
            return True


def _copy_rec(r: ResearchSessionRecord) -> ResearchSessionRecord:
    return ResearchSessionRecord(
        session_id=r.session_id,
        topic=r.topic,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
        use_hydra=r.use_hydra,
        hydra_connected=r.hydra_connected,
        error=r.error,
        outcome=dict(r.outcome) if r.outcome else None,
        transcript=list(r.transcript),
    )


# Replaced at startup by :func:`init_session_store`. Do not ``from session_store import store`` in
# route modules — that binds the *initial* instance; use ``import session_store`` and
# ``session_store.store`` so calls go to Mongo after lifespan runs.
store: AbstractSessionStore = MemorySessionStore()


async def init_session_store(
    *,
    memory: bool = False,
    mongo_uri: str | None = None,
    mongo_db: str = "ai_researcher",
    mongo_collection: str = "research_sessions",
) -> None:
    """
    Call from app lifespan. ``memory=True`` uses a pure in-process dict store.
    ``mongo_uri`` selects MongoDB (Motor) for durable sessions.
    """
    global store
    if memory:
        store = MemorySessionStore()
        return
    if mongo_uri:
        from .mongo_session_store import MongoSessionStore

        tmp = MongoSessionStore(mongo_uri, mongo_db, mongo_collection)
        await tmp.init_indexes()
        store = tmp
        return
    store = MemorySessionStore()
