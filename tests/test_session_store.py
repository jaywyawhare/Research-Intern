from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("aiosqlite")


def test_sqlite_session_roundtrip(tmp_path: Path) -> None:
    from backend.session_store import SqliteSessionStore

    async def run() -> None:
        dbp = tmp_path / "s.db"
        s = SqliteSessionStore(str(dbp))
        await s.init_schema()
        rec = await s.create("  quantum  ", use_hydra=False)
        sid = rec.session_id
        assert rec.status == "pending"
        await s.patch(sid, status="running")
        await s.patch(sid, status="ready", outcome={"topic": "quantum", "papers": []})
        await s.append_transcript(sid, {"role": "user", "content": "hi", "ts": 1.0})
        g = await s.get(sid)
        assert g is not None
        assert g.status == "ready"
        assert len(g.transcript) == 1
        assert (tmp_path / "s.db").exists()

    asyncio.run(run())
