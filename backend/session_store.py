from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SessionStatus = Literal["pending", "running", "ready", "error"]

_UNSET: Any = object()


def _import_aiosqlite():
    try:
        import aiosqlite
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "SQLite session storage requires the aiosqlite package. "
            "Install with: pip install aiosqlite   (or pip install -r requirements.txt)"
        ) from e
    return aiosqlite


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


class SqliteSessionStore(AbstractSessionStore):
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    def new_session_id(self) -> str:
        return f"sess_{uuid.uuid4().hex[:20]}"

    async def _conn(self):
        aiosqlite = _import_aiosqlite()
        db = await aiosqlite.connect(self.path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        return db

    async def init_schema(self) -> None:
        aiosqlite = _import_aiosqlite()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS research_sessions (
                    session_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    use_hydra INTEGER NOT NULL,
                    hydra_connected INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    outcome_json TEXT,
                    transcript_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            await db.commit()

    def _row_to_rec(self, row: Any) -> ResearchSessionRecord:
        oj = row["outcome_json"]
        tj = row["transcript_json"] or "[]"
        return ResearchSessionRecord(
            session_id=row["session_id"],
            topic=row["topic"],
            status=row["status"],
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            use_hydra=bool(row["use_hydra"]),
            hydra_connected=bool(row["hydra_connected"]),
            error=row["error"],
            outcome=json.loads(oj) if oj else None,
            transcript=json.loads(tj) if tj else [],
        )

    async def create(self, topic: str, *, use_hydra: bool) -> ResearchSessionRecord:
        now = time.time()
        sid = self.new_session_id()
        async with self._lock:
            db = await self._conn()
            try:
                await db.execute(
                    """
                    INSERT INTO research_sessions (
                        session_id, topic, status, created_at, updated_at,
                        use_hydra, hydra_connected, error, outcome_json, transcript_json
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL, NULL, '[]')
                    """,
                    (sid, topic.strip(), "pending", now, now, int(use_hydra)),
                )
                await db.commit()
            finally:
                await db.close()
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
            db = await self._conn()
            try:
                cur = await db.execute(
                    "SELECT * FROM research_sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = await cur.fetchone()
                return self._row_to_rec(row) if row else None
            finally:
                await db.close()

    async def list_summaries(self) -> list[ResearchSessionRecord]:
        async with self._lock:
            db = await self._conn()
            try:
                cur = await db.execute(
                    "SELECT * FROM research_sessions ORDER BY created_at DESC"
                )
                rows = await cur.fetchall()
                return [self._row_to_rec(r) for r in rows]
            finally:
                await db.close()

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
            db = await self._conn()
            try:
                cur = await db.execute(
                    "SELECT * FROM research_sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = await cur.fetchone()
                if row is None:
                    return
                rec = self._row_to_rec(row)
                if status is not None:
                    rec.status = status
                if error is not _UNSET:
                    rec.error = error
                if outcome is not _UNSET:
                    rec.outcome = outcome
                if hydra_connected is not None:
                    rec.hydra_connected = hydra_connected
                rec.updated_at = time.time()
                ojson = json.dumps(rec.outcome) if rec.outcome is not None else None
                await db.execute(
                    """
                    UPDATE research_sessions SET
                        status = ?, updated_at = ?, error = ?,
                        outcome_json = ?, hydra_connected = ?
                    WHERE session_id = ?
                    """,
                    (
                        rec.status,
                        rec.updated_at,
                        rec.error,
                        ojson,
                        int(rec.hydra_connected),
                        session_id,
                    ),
                )
                await db.commit()
            finally:
                await db.close()

    async def delete(self, session_id: str) -> bool:
        async with self._lock:
            db = await self._conn()
            try:
                cur = await db.execute(
                    "DELETE FROM research_sessions WHERE session_id = ?",
                    (session_id,),
                )
                await db.commit()
                return cur.rowcount > 0
            finally:
                await db.close()

    async def append_transcript(self, session_id: str, entry: dict[str, Any]) -> bool:
        async with self._lock:
            db = await self._conn()
            try:
                cur = await db.execute(
                    "SELECT transcript_json FROM research_sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = await cur.fetchone()
                if row is None:
                    return False
                tr = json.loads(row[0] or "[]")
                tr.append(entry)
                now = time.time()
                await db.execute(
                    """
                    UPDATE research_sessions SET transcript_json = ?, updated_at = ?
                    WHERE session_id = ?
                    """,
                    (json.dumps(tr), now, session_id),
                )
                await db.commit()
                return True
            finally:
                await db.close()


store: AbstractSessionStore = MemorySessionStore()


async def init_session_store(
    *,
    path: str | None = None,
    memory: bool = False,
) -> None:
    """
    Call from app lifespan. ``memory=True`` uses a pure in-process dict store.
    ``path=\":memory:\"`` uses SQLite in RAM. A file ``path`` persists sessions.
    """
    global store
    if memory:
        store = MemorySessionStore()
        return
    if path == ":memory:":
        tmp = SqliteSessionStore(":memory:")
        await tmp.init_schema()
        store = tmp
        return
    if path:
        tmp = SqliteSessionStore(path)
        await tmp.init_schema()
        store = tmp
        return
    store = MemorySessionStore()
