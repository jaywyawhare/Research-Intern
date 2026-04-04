from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Mapping

from hydra_db import AsyncHydraDB
from hydra_db.types.memory_item import MemoryItem

from . import config as hydra_config
from .context_builder import build_context_string
from .upload_retry import run_with_upload_retries

logger = logging.getLogger(__name__)


def _slug(s: str, max_len: int = 48) -> str:
    x = re.sub(r"[^a-zA-Z0-9_-]+", "_", s.strip())[:max_len]
    return x or "doc"


def _pydantic_to_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        return raw.model_dump(mode="json")
    if hasattr(raw, "dict"):
        return raw.dict()  # type: ignore[no-any-return]
    return json.loads(json.dumps(raw, default=str))


class HydraResearchBridge:
    def __init__(
        self,
        tenant_id: str | None = None,
        sub_tenant_id: str | None = None,
        *,
        token: str | None = None,
        http_timeout_seconds: float | None = None,
    ) -> None:
        hydra_config.load_dotenv()
        api_key = token or os.environ.get("HYDRADB_API_KEY") or os.environ.get("HYDRA_DB_API_KEY")
        if not api_key:
            raise ValueError("Missing HYDRADB_API_KEY or HYDRA_DB_API_KEY")
        tid = tenant_id or os.environ.get("HYDRADB_TENANT_ID") or os.environ.get("HYDRA_DB_TENANT_ID")
        if not tid:
            raise ValueError("Missing HYDRADB_TENANT_ID or HYDRA_DB_TENANT_ID")

        self._client = AsyncHydraDB(
            token=api_key,
            timeout=hydra_config.http_timeout_seconds(http_timeout_seconds),
        )
        self.tenant_id = tid
        self.sub_tenant_id = (
            sub_tenant_id
            if sub_tenant_id is not None
            else (os.environ.get("HYDRADB_SUB_TENANT_ID") or os.environ.get("HYDRA_DB_SUB_TENANT_ID") or "")
        )

    def _tenant_kwargs(self) -> dict[str, Any]:
        k: dict[str, Any] = {"tenant_id": self.tenant_id}
        if self.sub_tenant_id:
            k["sub_tenant_id"] = self.sub_tenant_id
        return k

    async def gather_context_for_topic(
        self,
        topic: str,
        *,
        metadata_filters: Mapping[str, Any] | None = None,
    ) -> dict[str, str]:
        base = self._tenant_kwargs()
        if metadata_filters:
            base = {**base, "metadata_filters": dict(metadata_filters)}
        q = topic.strip()
        pref = await self._client.recall.recall_preferences(query=q, **base)
        full = await self._client.recall.full_recall(query=q, **base)
        return {
            "user_context": build_context_string(_pydantic_to_dict(pref)),
            "knowledge_context": build_context_string(_pydantic_to_dict(full)),
        }

    async def ingest_markdown_source(
        self,
        *,
        session_id: str,
        topic: str,
        title: str,
        body_md: str,
        source_url: str,
        extra_document_metadata: Mapping[str, Any] | None = None,
        upsert: bool = True,
    ) -> None:
        fname = f"{_slug(title)}.md"
        content = body_md.encode("utf-8")
        meta = json.dumps(
            [
                {
                    "metadata": {
                        "session_id": session_id,
                        "topic": topic,
                        "source_url": source_url,
                    },
                    "additional_metadata": dict(extra_document_metadata or {}),
                }
            ]
        )

        async def op() -> Any:
            return await self._client.upload.knowledge(
                **self._tenant_kwargs(),
                upsert=upsert,
                files=[(fname, content)],
                file_metadata=meta,
            )

        await run_with_upload_retries(op, logger=logger)

    async def _add_memory(self, item: MemoryItem, *, upsert: bool = True) -> None:
        await self._client.upload.add_memory(memories=[item], upsert=upsert, **self._tenant_kwargs())

    async def save_thinking_step(
        self,
        *,
        session_id: str,
        step_index: int,
        title: str,
        text: str,
        infer: bool = True,
    ) -> None:
        sid = f"research_intern/{session_id}/thinking_{step_index}"
        meta = json.dumps({"kind": "thinking_step", "session_id": session_id, "step": step_index})
        await self._add_memory(
            MemoryItem(
                source_id=sid,
                title=title[:500],
                text=text,
                infer=infer,
                is_markdown=True,
                document_metadata=meta,
            ),
        )

    async def save_session_synthesis(
        self,
        *,
        session_id: str,
        text: str,
        title: str = "Session synthesis",
        infer: bool = True,
    ) -> None:
        sid = f"research_intern/{session_id}/synthesis"
        meta = json.dumps({"kind": "session_synthesis", "session_id": session_id})
        await self._add_memory(
            MemoryItem(
                source_id=sid,
                title=title[:500],
                text=text,
                infer=infer,
                is_markdown=True,
                document_metadata=meta,
            ),
        )
