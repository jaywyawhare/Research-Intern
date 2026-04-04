from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from .arxiv_literature import PaperRecord, corpus_metrics, fetch_recent_papers
from .open_http_literature import (
    fetch_crossref_records,
    fetch_europepmc_records,
    fetch_openalex_records,
    fetch_pubmed_records,
    fetch_semantic_scholar_records,
    fetch_wikipedia_records,
    shared_http_client,
)
from .prompts import build_analysis_prompt

if TYPE_CHECKING:
    from .hydra_research_bridge import HydraResearchBridge

logger = logging.getLogger(__name__)

build_research_intern_analysis_prompt = build_analysis_prompt


@dataclass(frozen=True)
class LiteraturePhaseOutcome:
    topic: str
    session_id: str
    papers: tuple[PaperRecord, ...]
    arxiv_search_query: str
    extra_source_summary: str
    corpus_stats: dict[str, Any]
    user_context: str
    knowledge_context: str
    analysis_prompt: str


def _corpus_ingest_body(p: PaperRecord) -> str:
    lines = [
        f"**Source:** {p.source}",
        f"**ID:** `{p.arxiv_id}`",
        f"**Published:** {p.published}",
    ]
    if p.authors:
        lines.append(f"**Authors:** {', '.join(p.authors[:20])}")
    if p.venue:
        lines.append(f"**Venue:** {p.venue}")
    if p.citation_count:
        lines.append(f"**Citation count:** {p.citation_count}")
    lines.extend(["", "## Text", "", p.summary])
    return "\n".join(lines)


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
    bridge: HydraResearchBridge | None,
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
    wikipedia_max: int = 2,
    crossref_max: int = 4,
    europepmc_max: int = 0,
    pubmed_max: int = 0,
    openalex_max: int = 0,
    semantic_scholar_max: int = 0,
    crossref_mailto: str | None = None,
) -> LiteraturePhaseOutcome:
    """
    Load Hydra context, fetch recent arXiv papers for ``topic``, optionally ingest each
    into the knowledge base, then build the analysis prompt.

    Pass ``bridge=None`` to skip Hydra recall and ingestion (fetches + prompt only).

    **Keyless / optional-key sources:** Wikipedia, Crossref, **OpenAlex** (identifying
    ``User-Agent`` with mail), **Semantic Scholar** (slow path: ~1 s between calls; optional
    ``SEMANTIC_SCHOLAR_API_KEY`` for higher limits), Europe PMC, PubMed (NCBI ``tool``/``email``).
    Set each ``*_max`` to ``0`` to disable.

    By default the arXiv query is a **phrase** search scoped to cs.CL / cs.AI / cs.LG / stat.ML
    so broad words like “model” do not match unrelated fields. Set ``restrict_arxiv_cs_stat_ml=False``
    for other disciplines, or ``raw_arxiv_query=True`` to pass ``topic`` through as a full API query.

    Use ``restrict_recall_to_session=True`` to pass ``metadata_filters`` so Hydra recall only sees
    knowledge/memories tagged with this ``session_id`` (reduces cross-session noise). Stale or
    off-topic chunks already stored under the same session must be removed in the Hydra UI or by
    using a fresh ``session_id``.

    ``ingest_pause_seconds`` adds a short delay between uploads to ease rate limits and server load.
    """
    if bridge is None:
        user_ctx, know_ctx = "", ""
        if restrict_recall_to_session or recall_metadata_filters:
            logger.warning("recall filters ignored without a HydraResearchBridge")
        if ingest_to_knowledge:
            logger.warning("ingest_to_knowledge ignored without a HydraResearchBridge")
    else:
        recall_filters = _recall_filters_for_session(
            session_id, restrict_recall_to_session, recall_metadata_filters
        )
        ctx = await bridge.gather_context_for_topic(topic, metadata_filters=recall_filters)
        user_ctx = ctx.get("user_context") or ""
        know_ctx = ctx.get("knowledge_context") or ""

    async def _no_extra() -> tuple[PaperRecord, ...]:
        return ()

    async with shared_http_client() as http:
        arxiv_coro = fetch_recent_papers(
            topic,
            max_results=max_papers,
            restrict_cs_stat_ml=restrict_arxiv_cs_stat_ml,
            raw_arxiv_query=raw_arxiv_query,
            client=http,
        )
        wiki_coro = (
            fetch_wikipedia_records(topic, max_results=wikipedia_max, client=http)
            if wikipedia_max > 0
            else _no_extra()
        )
        xf_coro = (
            fetch_crossref_records(
                topic, max_results=crossref_max, client=http, mailto=crossref_mailto
            )
            if crossref_max > 0
            else _no_extra()
        )
        epm_coro = (
            fetch_europepmc_records(topic, max_results=europepmc_max, client=http)
            if europepmc_max > 0
            else _no_extra()
        )
        pm_coro = (
            fetch_pubmed_records(topic, max_results=pubmed_max, client=http)
            if pubmed_max > 0
            else _no_extra()
        )
        oa_coro = (
            fetch_openalex_records(topic, max_results=openalex_max, client=http)
            if openalex_max > 0
            else _no_extra()
        )
        s2_coro = (
            fetch_semantic_scholar_records(topic, max_results=semantic_scholar_max, client=http)
            if semantic_scholar_max > 0
            else _no_extra()
        )
        arxiv, wiki, xref, oa, s2, epmc, pubmed = await asyncio.gather(
            arxiv_coro, wiki_coro, xf_coro, oa_coro, s2_coro, epm_coro, pm_coro
        )

    arxiv_q = arxiv.search_query
    ptuple = arxiv.papers + wiki + xref + oa + s2 + epmc + pubmed
    stats = corpus_metrics(ptuple)

    extra_lines: list[str] = []
    if wikipedia_max > 0:
        extra_lines.append(
            f"- Wikipedia (MediaWiki opensearch + REST summary): requested up to {wikipedia_max}, got {len(wiki)}."
        )
    if crossref_max > 0:
        extra_lines.append(
            f"- Crossref /works (public JSON, no key): requested up to {crossref_max}, got {len(xref)}."
        )
    if europepmc_max > 0:
        extra_lines.append(
            f"- Europe PMC REST search (no key): requested up to {europepmc_max}, got {len(epmc)}."
        )
    if pubmed_max > 0:
        extra_lines.append(
            f"- PubMed (NCBI E-utilities, no API key): requested up to {pubmed_max}, got {len(pubmed)}."
        )
    if openalex_max > 0:
        extra_lines.append(
            f"- OpenAlex works (no key; polite User-Agent): requested up to {openalex_max}, got {len(oa)}."
        )
    if semantic_scholar_max > 0:
        extra_lines.append(
            f"- Semantic Scholar paper search: requested up to {semantic_scholar_max}, got {len(s2)}."
        )
    extra_source_summary = "\n".join(extra_lines)

    if ingest_to_knowledge and bridge is not None:
        n = len(ptuple)
        for i, p in enumerate(ptuple):
            await bridge.ingest_markdown_source(
                session_id=session_id,
                topic=topic,
                title=p.title[:500],
                body_md=_corpus_ingest_body(p),
                source_url=p.abs_url,
                extra_document_metadata={
                    "record_id": p.arxiv_id,
                    "source": p.source,
                    "published": p.published,
                    "venue": p.venue,
                    "citation_count": p.citation_count,
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
        extra_source_summary=extra_source_summary,
    )

    return LiteraturePhaseOutcome(
        topic=topic,
        session_id=session_id,
        papers=ptuple,
        arxiv_search_query=arxiv_q,
        extra_source_summary=extra_source_summary,
        corpus_stats=stats,
        user_context=user_ctx,
        knowledge_context=know_ctx,
        analysis_prompt=prompt,
    )
