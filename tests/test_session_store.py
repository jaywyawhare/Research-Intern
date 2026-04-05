from __future__ import annotations

import asyncio

from backend.session_store import MemorySessionStore


def test_memory_session_roundtrip() -> None:
    async def run() -> None:
        s = MemorySessionStore()
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

    asyncio.run(run())
