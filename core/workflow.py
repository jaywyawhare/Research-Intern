from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING, Any, Mapping

from . import config as hydra_config
from .arxiv_literature import PaperRecord, corpus_metrics, fetch_recent_papers
from .llm_completion import run_analysis_completion
from .open_http_literature import (
    fetch_crossref_records,
    fetch_europepmc_records,
    fetch_openalex_records,
    fetch_pubmed_records,
    fetch_semantic_scholar_records,
    fetch_wikipedia_records,
    shared_http_client,
)
from .knowledge_graph_view import build_knowledge_graph_view
from .prompts import build_analysis_prompt

if TYPE_CHECKING:
    from .hydra_research_bridge import HydraResearchBridge

logger = logging.getLogger(__name__)

build_research_intern_analysis_prompt = build_analysis_prompt


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/extra whitespace for fuzzy title matching."""
    t = title.lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def _paper_dedup_keys(p: PaperRecord) -> list[str]:
    """
    Return all canonical dedup keys for a paper.

    A paper can match via DOI, real arXiv ID, or normalized title hash.
    Cross-source duplicates will share at least one key.
    """
    keys: list[str] = []

    doi = getattr(p, 'doi', '') or ''
    if doi.strip():
        keys.append(f'doi:{doi.strip().lower()}')

    aid = p.arxiv_id or ''
    if aid.strip():
        raw = aid.strip().lower()
        is_real_arxiv = (
            (raw.startswith('arxiv:') and '.' in raw)
            or re.match(r'^\d{4}\.\d{4,5}$', raw) is not None
            or re.match(r'^[a-z-]+/\d{7}$', raw) is not None
        )
        if is_real_arxiv:
            keys.append(f'arxiv:{raw}' if not raw.startswith('arxiv:') else raw)

    title_key = _normalize_title(p.title)
    if title_key:
        h = hashlib.md5(title_key.encode()).hexdigest()[:12]
        keys.append(f'title:{h}')

    if not keys:
        keys.append(f'unknown:{p.abs_url or p.source}')

    return keys


def _paper_dedup_key(p: PaperRecord) -> str:
    """Return the primary dedup key for a paper (first of _paper_dedup_keys)."""
    return _paper_dedup_keys(p)[0]


def _deduplicate_papers(papers: list[PaperRecord]) -> list[PaperRecord]:
    """
    Remove duplicate papers across sources.

    Two papers are considered duplicates if they share ANY dedup key
    (same DOI, same arXiv ID, or same normalized title hash).
    Keeps the first occurrence (preferring earlier sources in the pipeline order).
    """
    seen_keys: dict[str, PaperRecord] = {}
    kept: list[PaperRecord] = []
    removed = 0

    for p in papers:
        keys = _paper_dedup_keys(p)
        is_dup = False
        for k in keys:
            if k in seen_keys:
                is_dup = True
                removed += 1
                logger.debug(
                    "Dedup removed: %r (duplicate of %r via key=%s)",
                    p.title[:80], seen_keys[k].title[:80], k,
                )
                break

        if not is_dup:
            for k in keys:
                seen_keys[k] = p
            kept.append(p)

    if removed:
        logger.info("Deduplicated papers: kept %d, removed %d duplicates", len(kept), removed)

    return kept


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
    final_analysis: str | None = None
    knowledge_graph: dict[str, Any] | None = None
    visited_sources: list[str] | None = None


def paper_record_to_ingest_markdown(p: PaperRecord) -> str:
    """Markdown body uploaded to Hydra for a structured corpus paper (same shape as initial run)."""
    return _corpus_ingest_body(p)


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
    llm_complete: bool = False,
    openai_api_key: str | None = None,
    openai_model: str | None = None,
    openai_base_url: str | None = None,
    openai_top_p: float | None = None,
    openai_max_tokens: int | None = None,
    openai_extra_body: dict[str, Any] | None = None,
    llm_stream: bool | None = None,
    llm_stream_to: IO[str] | None = None,
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

    Set ``llm_complete=True`` to call an OpenAI-compatible chat API with the built prompt and
    store the assistant reply in ``final_analysis`` (needs ``OPENAI_API_KEY``, ``NVIDIA_API_KEY``,
    or ``openai_api_key``). Use ``llm_stream=True`` to stream chunks to ``llm_stream_to`` (default
    ``sys.stderr``). Provider-specific JSON can be passed via ``openai_extra_body`` or env
    ``OPENAI_EXTRA_BODY``; throttle with ``OPENAI_MAX_RPM`` (e.g. ``30``).
    """
    knowledge_graph: dict[str, Any] | None = None
    if bridge is None:
        user_ctx, know_ctx = "", ""
        if restrict_recall_to_session or recall_metadata_filters:
            logger.warning("recall filters ignored without a HydraResearchBridge")
        if ingest_to_knowledge:
            logger.warning("ingest_to_knowledge ignored without a HydraResearchBridge")
    else:
        logger.info("session %s: calling Hydra recall for topic='%s'", session_id, topic)
        recall_filters = _recall_filters_for_session(
            session_id, restrict_recall_to_session, recall_metadata_filters
        )
        ctx = await bridge.gather_context_for_topic(topic, metadata_filters=recall_filters)
        logger.info("session %s: Hydra recall complete", session_id)
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
    all_papers = arxiv.papers + wiki + xref + oa + s2 + epmc + pubmed
    ptuple = tuple(_deduplicate_papers(all_papers))
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
        logger.info("session %s: starting ingest of %d papers", session_id, len(ptuple))
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
            if i % 5 == 0:
                logger.info("session %s: ingested %d/%d papers", session_id, i + 1, n)
            if ingest_pause_seconds > 0 and i < n - 1:
                await asyncio.sleep(ingest_pause_seconds)
        logger.info("session %s: ingest complete, waiting for indexing", session_id)

        await asyncio.sleep(5)

        ctx_after = await bridge.gather_context_for_topic(topic, metadata_filters=recall_filters)
        user_ctx = ctx_after.get("user_context") or ""
        know_ctx = ctx_after.get("knowledge_context") or ""

        ctx_for_graph = await bridge.gather_context_for_topic(topic)
        full_raw_after = ctx_for_graph.get("full_recall_raw")
        pref_raw_after = ctx_for_graph.get("recall_preferences_raw")
        if isinstance(full_raw_after, dict) or isinstance(pref_raw_after, dict):
            knowledge_graph = build_knowledge_graph_view(
                full_raw_after if isinstance(full_raw_after, dict) else None,
                pref_raw_after if isinstance(pref_raw_after, dict) else None,
            )
            logger.info(
                "Knowledge graph built after ingest: %d nodes, %d edges, %d paths",
                knowledge_graph.get("stats", {}).get("node_count", 0),
                knowledge_graph.get("stats", {}).get("edge_count", 0),
                knowledge_graph.get("stats", {}).get("path_count", 0),
            )

    prompt = build_analysis_prompt(
        topic=topic,
        user_context=user_ctx,
        knowledge_context=know_ctx,
        papers=ptuple,
        arxiv_search_query=arxiv_q,
        extra_source_summary=extra_source_summary,
    )

    final: str | None = None
    if llm_complete:
        hydra_config.load_dotenv()
        key = (openai_api_key or "").strip()
        if not key:
            key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get(
                "NVIDIA_API_KEY", ""
            ).strip()
        if not key:
            raise ValueError(
                "llm_complete requires OPENAI_API_KEY / NVIDIA_API_KEY or openai_api_key="
            )
        sink = None
        if llm_stream is True:
            out = llm_stream_to or sys.stderr

            def sink(s: str) -> None:
                out.write(s)
                out.flush()

        final = await run_analysis_completion(
            prompt,
            api_key=key,
            model=openai_model,
            base_url=openai_base_url,
            top_p=openai_top_p,
            max_tokens=openai_max_tokens,
            extra_body=openai_extra_body,
            stream=llm_stream,
            stream_sink=sink,
        )

    visited_sources = [_paper_dedup_key(p) for p in ptuple]

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
        final_analysis=final,
        knowledge_graph=knowledge_graph,
        visited_sources=visited_sources,
    )


async def regenerate_session_knowledge_graph(
    bridge: HydraResearchBridge,
    *,
    topic: str,
    session_id: str,
    restrict_recall_to_session: bool = False,
    recall_metadata_filters: Mapping[str, Any] | None = None,
    run_llm: bool = True,
    existing_papers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Re-run Hydra recall for a session's topic and rebuild the knowledge graph.
    Optionally re-run LLM analysis with the updated graph.
    Returns a dict suitable for patching the session outcome.
    """
    recall_filters = _recall_filters_for_session(
        session_id, restrict_recall_to_session, recall_metadata_filters
    )
    ctx = await bridge.gather_context_for_topic(topic, metadata_filters=recall_filters)
    user_ctx = ctx.get("user_context") or ""
    know_ctx = ctx.get("knowledge_context") or ""
    full_raw = ctx.get("full_recall_raw")
    pref_raw = ctx.get("recall_preferences_raw")

    knowledge_graph: dict[str, Any] | None = None
    if isinstance(full_raw, dict) or isinstance(pref_raw, dict):
        knowledge_graph = build_knowledge_graph_view(
            full_raw if isinstance(full_raw, dict) else None,
            pref_raw if isinstance(pref_raw, dict) else None,
        )
        logger.info(
            "Knowledge graph regenerated: session_id=%s nodes=%d edges=%d paths=%d",
            session_id,
            knowledge_graph.get("stats", {}).get("node_count", 0),
            knowledge_graph.get("stats", {}).get("edge_count", 0),
            knowledge_graph.get("stats", {}).get("path_count", 0),
        )

    final_analysis = None
    synthesis_error: str | None = None
    analysis_prompt: str | None = None
    if run_llm:
        paper_rows = existing_papers or []
        ptuple = [
            PaperRecord(
                arxiv_id=p.get("arxiv_id", ""),
                title=p.get("title", ""),
                summary=p.get("summary", ""),
                published=p.get("published", ""),
                abs_url=p.get("abs_url", ""),
                source=p.get("source", "arxiv"),
                authors=tuple(p.get("authors", [])),
                venue=p.get("venue", ""),
                citation_count=p.get("citation_count", 0),
            )
            for p in paper_rows
        ]
        arxiv_q = f"all:\"{topic}\""
        prompt = build_analysis_prompt(
            topic=topic,
            user_context=user_ctx,
            knowledge_context=know_ctx,
            papers=tuple(ptuple),
            arxiv_search_query=arxiv_q,
            extra_source_summary="",
        )
        analysis_prompt = prompt
        hydra_config.load_dotenv()
        key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("NVIDIA_API_KEY", "").strip()
        if not key:
            synthesis_error = "No OPENAI_API_KEY or NVIDIA_API_KEY is set; synthesis was skipped."
        else:
            try:
                final_analysis = await run_analysis_completion(prompt, stream=False)
                logger.info("LLM analysis re-run complete for session %s", session_id)
            except Exception as e:
                err = str(e).strip() or repr(e)
                synthesis_error = err[:2000]
                logger.warning("LLM re-analysis failed for session %s: %s", session_id, e)

    out: dict[str, Any] = {
        "knowledge_graph": knowledge_graph,
        "user_context": user_ctx,
        "knowledge_context": know_ctx,
    }
    if run_llm:
        out["analysis_prompt"] = analysis_prompt
        out["final_analysis"] = final_analysis
        out["synthesis_error"] = synthesis_error
    return out
