from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping

from .arxiv_literature import PaperRecord, fetch_recent_papers
from .hydra_research_bridge import HydraResearchBridge
from .prompts import build_analysis_prompt

build_research_intern_analysis_prompt = build_analysis_prompt


@dataclass(frozen=True)
class LiteraturePhaseOutcome:
    topic: str
    session_id: str
    papers: tuple[PaperRecord, ...]
    arxiv_search_query: str
    user_context: str
    knowledge_context: str
    analysis_prompt: str


def _arxiv_ingest_body(p: PaperRecord) -> str:
    return (
        f"**arXiv:** `{p.arxiv_id}`\n**Published:** {p.published}\n\n"
        f"## Abstract\n\n{p.summary}"
    )


def _recall_filters_for_session(
    session_id: str,
    restrict_recall_to_session: bool,
    recall_metadata_filters: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    meta: dict[str, Any] = dict(recall_metadata_filters) if recall_metadata_filters else {}
    if restrict_recall_to_session:
        meta.setdefault("session_id", session_id)
    return meta if meta else None


async def run_literature_phase(
    bridge: HydraResearchBridge,
    *,
    topic: str,
    session_id: str,
    max_papers: int = 30,
    ingest_to_knowledge: bool = True,
    restrict_arxiv_cs_stat_ml: bool = True,
    raw_arxiv_query: bool = False,
    recall_metadata_filters: Mapping[str, Any] | None = None,
    restrict_recall_to_session: bool = False,
    ingest_pause_seconds: float = 0.6,
) -> LiteraturePhaseOutcome:
    """
    Load Hydra context, fetch recent arXiv papers for ``topic``, optionally ingest each
    into the knowledge base, then build the analysis prompt.

    By default the arXiv query is a **phrase** search scoped to cs.CL / cs.AI / cs.LG / stat.ML
    so broad words like “model” do not match unrelated fields. Set ``restrict_arxiv_cs_stat_ml=False``
    for other disciplines, or ``raw_arxiv_query=True`` to pass ``topic`` through as a full API query.

    Use ``restrict_recall_to_session=True`` to pass ``metadata_filters`` so Hydra recall only sees
    knowledge/memories tagged with this ``session_id`` (reduces cross-session noise). Stale or
    off-topic chunks already stored under the same session must be removed in the Hydra UI or by
    using a fresh ``session_id``.

    ``ingest_pause_seconds`` adds a short delay between uploads to ease rate limits and server load.
    """
    recall_filters = _recall_filters_for_session(
        session_id, restrict_recall_to_session, recall_metadata_filters
    )
    ctx = await bridge.gather_context_for_topic(topic, metadata_filters=recall_filters)
    user_ctx = ctx.get("user_context") or ""
    know_ctx = ctx.get("knowledge_context") or ""

    arxiv = await fetch_recent_papers(
        topic,
        max_results=max_papers,
        restrict_cs_stat_ml=restrict_arxiv_cs_stat_ml,
        raw_arxiv_query=raw_arxiv_query,
    )
    ptuple = arxiv.papers
    arxiv_q = arxiv.search_query

    if ingest_to_knowledge:
        n = len(ptuple)
        for i, p in enumerate(ptuple):
            await bridge.ingest_markdown_source(
                session_id=session_id,
                topic=topic,
                title=p.title[:500],
                body_md=_arxiv_ingest_body(p),
                source_url=p.abs_url,
                extra_document_metadata={
                    "arxiv_id": p.arxiv_id,
                    "source": "arxiv",
                    "published": p.published,
                },
            )
            if ingest_pause_seconds > 0 and i < n - 1:
                await asyncio.sleep(ingest_pause_seconds)

    prompt = build_analysis_prompt(
        topic=topic,
        user_context=user_ctx,
        knowledge_context=know_ctx,
        papers=ptuple,
        arxiv_search_query=arxiv_q,
    )

    return LiteraturePhaseOutcome(
        topic=topic,
        session_id=session_id,
        papers=ptuple,
        arxiv_search_query=arxiv_q,
        user_context=user_ctx,
        knowledge_context=know_ctx,
        analysis_prompt=prompt,
    )
