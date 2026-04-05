from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Query
from starlette.responses import StreamingResponse

from core.arxiv_beam import arxiv_beam_expand, paper_record_to_store_dict, store_dict_to_paper_record
from core.arxiv_literature import corpus_metrics
from core.open_http_literature import shared_http_client
from core.workflow import paper_record_to_ingest_markdown, run_literature_phase

from ..agents.orchestrator import run_multi_agent_turn
from ..context_util import session_retrieval_context
from ..hydra_util import try_hydra_bridge
from ..params import corpus_maxima
from ..schemas import (
    AddSourceRequest,
    AddSourceResponse,
    ArxivBeamExtendRequest,
    ArxivBeamExtendResponse,
    MultiAgentTurnRequest,
    MultiAgentTurnResponse,
    RegenerateGraphRequest,
    RegenerateGraphResponse,
    SessionAskRequest,
    SessionAskResponse,
    SessionCreateRequest,
    SessionCreatedResponse,
    SessionDetailResponse,
    SessionSummary,
    TranscriptTurn,
    literature_outcome_to_store,
    stored_outcome_to_response,
)
from .. import session_store
from ..error_format import format_stored_session_error
from ..session_store import ResearchSessionRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


def _merge_regeneration_outcome(current: dict[str, Any] | None, result: dict[str, Any]) -> dict[str, Any]:
    """Append previous synthesis to history when a new analysis is produced; omit None patches."""
    out = dict(current or {})
    prev_fa = out.get("final_analysis")
    new_fa = result.get("final_analysis")
    if new_fa is not None and isinstance(prev_fa, str) and prev_fa.strip():
        hist = list(out.get("synthesis_history") or [])
        hist.insert(0, {"ts": time.time(), "text": prev_fa})
        out["synthesis_history"] = hist[:40]
    patch = {k: v for k, v in result.items() if v is not None}
    out.update(patch)
    if "synthesis_error" in result:
        se = result.get("synthesis_error")
        if se:
            out["synthesis_error"] = se
        else:
            out.pop("synthesis_error", None)
    return out


def _summary(rec: ResearchSessionRecord) -> SessionSummary:
    return SessionSummary(
        session_id=rec.session_id,
        topic=rec.topic,
        status=rec.status,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        use_hydra=rec.use_hydra,
        hydra_connected=rec.hydra_connected,
        error=rec.error,
    )


async def _run_session_job(session_id: str, body: SessionCreateRequest) -> None:
    topic = body.topic.strip()
    wiki_max, xref_max, epm_max, pm_max, oa_max, s2_max = corpus_maxima(body)
    await session_store.store.patch(session_id, status="running", error=None)
    bridge = try_hydra_bridge(body.use_hydra)
    await session_store.store.patch(session_id, hydra_connected=bridge is not None)
    try:
        outcome = await asyncio.wait_for(
            run_literature_phase(
                bridge,
                topic=topic,
                session_id=session_id,
                max_papers=body.max_papers,
                ingest_to_knowledge=body.ingest_to_knowledge,
                restrict_arxiv_cs_stat_ml=body.restrict_arxiv_cs_stat_ml,
                raw_arxiv_query=body.raw_arxiv_query,
                recall_metadata_filters=body.recall_metadata_filters,
                restrict_recall_to_session=body.restrict_recall_to_session,
                ingest_pause_seconds=body.ingest_pause_seconds,
                wikipedia_max=wiki_max,
                crossref_max=xref_max,
                europepmc_max=epm_max,
                pubmed_max=pm_max,
                openalex_max=oa_max,
                semantic_scholar_max=s2_max,
                crossref_mailto=body.crossref_mailto,
                llm_complete=not body.prompt_only,
                llm_stream=False,
            ),
            timeout=180,
        )
        blob = literature_outcome_to_store(outcome)
        await session_store.store.patch(session_id, status="ready", outcome=blob, error=None)
    except asyncio.TimeoutError:
        logger.error("session %s timed out after 180s", session_id)
        await session_store.store.patch(session_id, status="error", error="Session timed out after 180 seconds. Hydra API may be slow — try again or check Hydra status.")
    except Exception as e:
        logger.exception("session %s failed", session_id)
        await session_store.store.patch(session_id, status="error", error=format_stored_session_error(e))


@router.post("/", response_model=SessionCreatedResponse)
async def create_session(
    body: SessionCreateRequest,
    background_tasks: BackgroundTasks,
) -> SessionCreatedResponse:
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic must not be empty")
    rec = await session_store.store.create(topic, use_hydra=body.use_hydra)
    background_tasks.add_task(_run_session_job, rec.session_id, body)
    return SessionCreatedResponse(
        session_id=rec.session_id,
        status=rec.status,
        topic=rec.topic,
        use_hydra=rec.use_hydra,
    )


@router.get("/", response_model=list[SessionSummary])
async def list_sessions() -> list[SessionSummary]:
    rows = await session_store.store.list_summaries()
    return [_summary(r) for r in rows]


@router.get("/{session_id}/events")
async def session_status_events(session_id: str) -> StreamingResponse:
    """Server-Sent Events: periodic ``status`` until ``ready`` or ``error`` (or unknown session)."""

    async def gen():
        while True:
            rec = await session_store.store.get(session_id)
            if rec is None:
                yield f"data: {json.dumps({'event': 'not_found'})}\n\n".encode()
                break
            payload = {
                "event": "status",
                "session_id": session_id,
                "status": rec.status,
                "updated_at": rec.updated_at,
                "error": rec.error,
            }
            yield f"data: {json.dumps(payload)}\n\n".encode()
            if rec.status in ("ready", "error"):
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    include_analysis_prompt: bool = Query(default=True),
    include_papers: bool = Query(default=True),
) -> SessionDetailResponse:
    rec = await session_store.store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    outcome_resp = None
    if rec.outcome is not None and rec.status in ("ready", "error"):
        outcome_resp = stored_outcome_to_response(
            rec.outcome,
            include_analysis_prompt=include_analysis_prompt,
            include_papers=include_papers,
        )
    transcript = [
        TranscriptTurn(
            role=str(x.get("role", "")),
            content=str(x.get("content", "")),
            ts=float(x.get("ts", 0.0)),
            agent=x.get("agent") if isinstance(x.get("agent"), str) else None,
        )
        for x in rec.transcript
    ]
    base = _summary(rec)
    return SessionDetailResponse(
        **{**base.model_dump(), "outcome": outcome_resp, "transcript": transcript}
    )


@router.post("/{session_id}/retry", response_model=SessionCreatedResponse)
async def retry_failed_session(session_id: str, background_tasks: BackgroundTasks) -> SessionCreatedResponse:
    """
    Re-run the initial research job for a session that ended in ``error`` (e.g. Hydra timeout).
    Uses the same topic and ``use_hydra`` flag; other corpus options use :class:`SessionCreateRequest` defaults.
    """
    rec = await session_store.store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    if rec.status != "error":
        raise HTTPException(
            status_code=409,
            detail=f"Only failed sessions can be retried (status=error). Current status: {rec.status}",
        )
    body = SessionCreateRequest(topic=rec.topic.strip(), use_hydra=rec.use_hydra)
    await session_store.store.patch(
        session_id,
        status="running",
        error=None,
        outcome=None,
    )
    background_tasks.add_task(_run_session_job, session_id, body)
    return SessionCreatedResponse(
        session_id=rec.session_id,
        status="running",
        topic=rec.topic,
        use_hydra=rec.use_hydra,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    ok = await session_store.store.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")


@router.post("/{session_id}/agents/turn", response_model=MultiAgentTurnResponse)
async def multi_agent_turn(session_id: str, body: MultiAgentTurnRequest) -> MultiAgentTurnResponse:
    rec = await session_store.store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    if rec.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"session is {rec.status}; wait until ready or inspect error state",
        )
    msg = body.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message must not be empty")
    try:
        return await run_multi_agent_turn(
            rec,
            user_message=msg,
            force_agents=body.force_agents,
            run_auditor=body.run_auditor,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{session_id}/ask", response_model=SessionAskResponse)
async def ask_session(session_id: str, body: SessionAskRequest) -> SessionAskResponse:
    rec = await session_store.store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    if rec.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"session is {rec.status}; wait until ready or inspect error state",
        )
    if rec.outcome is None:
        raise HTTPException(status_code=500, detail="session has no stored outcome")

    q = body.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="question must not be empty")

    context, source = await session_retrieval_context(rec, session_id, q)

    if body.answer_with_llm:
        from core.llm_completion import run_analysis_completion

        prompt = (
            f'You answer questions about the research session on "{rec.topic}".\n\n'
            f"### Retrieved context\n{context}\n\n"
            f"### Question\n{q}\n\n"
            "Answer clearly from the context. If it is insufficient, say what is missing."
        )
        try:
            answer = await run_analysis_completion(prompt, stream=False)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        return SessionAskResponse(answer=answer, retrieved_context=context, context_source=source)

    return SessionAskResponse(answer=None, retrieved_context=context, context_source=source)


@router.post("/{session_id}/regenerate-graph", response_model=RegenerateGraphResponse)
async def regenerate_graph(
    session_id: str,
    background_tasks: BackgroundTasks,
    body: RegenerateGraphRequest = Body(
        default_factory=RegenerateGraphRequest,
        description="Omit or send {} to use defaults (LLM synthesis on).",
    ),
) -> RegenerateGraphResponse:
    rec = await session_store.store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    if not rec.use_hydra:
        raise HTTPException(status_code=400, detail="session was not created with Hydra; cannot regenerate graph")
    bridge = try_hydra_bridge(True)
    if bridge is None:
        raise HTTPException(status_code=503, detail="Hydra is not available")

    topic = rec.topic
    outcome = rec.outcome or {}
    existing_papers = outcome.get("papers", [])

    async def _do_regenerate():
        await session_store.store.patch(session_id, status="running", error=None)
        try:
            result = await _regenerate_knowledge_graph(
                bridge, topic, session_id, body.run_llm_analysis, existing_papers
            )
            current = await session_store.store.get(session_id)
            merged = _merge_regeneration_outcome(current.outcome if current else None, result)
            await session_store.store.patch(session_id, status="ready", error=None, outcome=merged)
        except Exception as e:
            logger.exception("session %s regenerate failed", session_id)
            await session_store.store.patch(session_id, status="error", error=format_stored_session_error(e))

    background_tasks.add_task(_do_regenerate)

    return RegenerateGraphResponse(
        session_id=session_id,
        topic=topic,
        knowledge_graph=outcome.get("knowledge_graph"),
        status="regenerating",
    )


@router.post("/{session_id}/add-sources", response_model=AddSourceResponse)
async def add_sources(
    session_id: str,
    body: AddSourceRequest,
    background_tasks: BackgroundTasks,
) -> AddSourceResponse:
    rec = await session_store.store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    if not rec.use_hydra:
        raise HTTPException(status_code=400, detail="session was not created with Hydra; cannot add sources")
    bridge = try_hydra_bridge(True)
    if bridge is None:
        raise HTTPException(status_code=503, detail="Hydra is not available")

    topic = rec.topic
    outcome = rec.outcome or {}
    existing_papers = outcome.get("papers", [])

    await bridge.ingest_markdown_source(
        session_id=session_id,
        topic=topic,
        title=body.title[:500],
        body_md=body.body_md,
        source_url=body.source_url or "",
        extra_document_metadata=body.extra_metadata or {},
    )

    async def _do_regenerate():
        await session_store.store.patch(session_id, status="running", error=None)
        try:
            await asyncio.sleep(5)
            result = await _regenerate_knowledge_graph(
                bridge, topic, session_id, run_llm=True, existing_papers=existing_papers
            )
            current = await session_store.store.get(session_id)
            merged = _merge_regeneration_outcome(current.outcome if current else None, result)
            await session_store.store.patch(session_id, status="ready", error=None, outcome=merged)
        except Exception as e:
            logger.exception("session %s add-sources regenerate failed", session_id)
            await session_store.store.patch(session_id, status="error", error=format_stored_session_error(e))

    background_tasks.add_task(_do_regenerate)

    return AddSourceResponse(
        session_id=session_id,
        source_title=body.title,
        knowledge_graph=outcome.get("knowledge_graph"),
        papers_count=len(existing_papers),
        status="processing",
    )


@router.post("/{session_id}/extend-arxiv-beam", response_model=ArxivBeamExtendResponse)
async def extend_arxiv_beam(
    session_id: str,
    body: ArxivBeamExtendRequest,
    background_tasks: BackgroundTasks,
) -> ArxivBeamExtendResponse:
    rec = await session_store.store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    if not rec.use_hydra:
        raise HTTPException(
            status_code=400,
            detail="session was not created with Hydra; cannot extend corpus",
        )
    bridge = try_hydra_bridge(True)
    if bridge is None:
        raise HTTPException(status_code=503, detail="Hydra is not available")

    topic = rec.topic
    outcome = rec.outcome or {}
    existing_papers = outcome.get("papers") or []
    existing_ids = {
        str(p.get("arxiv_id", "")).strip()
        for p in existing_papers
        if isinstance(p, dict) and (p.get("arxiv_id") or "").strip()
    }
    visited_sources = {
        s
        for s in (outcome.get("visited_sources") or [])
        if isinstance(s, str) and s.strip()
    }

    async def _beam_job() -> None:
        await session_store.store.patch(session_id, status="running", error=None)
        try:
            async with shared_http_client() as http:
                new_papers, queries = await arxiv_beam_expand(
                    topic,
                    existing_arxiv_ids=existing_ids,
                    visited_sources=visited_sources,
                    beam_width=body.beam_width,
                    depth=body.depth,
                    max_new_papers=body.max_new_papers,
                    restrict_cs_stat_ml=body.restrict_arxiv_cs_stat_ml,
                    raw_arxiv_query=body.raw_arxiv_query,
                    client=http,
                )
            b = try_hydra_bridge(True)
            if b is None:
                raise RuntimeError("Hydra is not available")
            papers = list(existing_papers)
            ingest_pause = 0.35
            new_source_keys: list[str] = []
            for i, p in enumerate(new_papers):
                await b.ingest_markdown_source(
                    session_id=session_id,
                    topic=topic,
                    title=p.title[:500],
                    body_md=paper_record_to_ingest_markdown(p),
                    source_url=p.abs_url,
                    extra_document_metadata={
                        "record_id": p.arxiv_id,
                        "source": p.source,
                        "published": p.published,
                        "venue": p.venue,
                        "citation_count": p.citation_count,
                    },
                )
                doi = getattr(p, 'doi', '') or ''
                if doi.strip():
                    pk = f'doi:{doi.strip().lower()}'
                elif p.arxiv_id:
                    raw = p.arxiv_id.strip().lower()
                    pk = f'arxiv:{raw}' if not raw.startswith('arxiv:') else raw
                else:
                    import re, hashlib
                    t = re.sub(r'[^a-z0-9\s]', '', p.title.lower().strip())
                    t = re.sub(r'\s+', ' ', t)
                    h = hashlib.md5(t.encode()).hexdigest()[:12]
                    pk = f'title:{h}' if t else f'unknown:{p.abs_url or p.source}'
                new_source_keys.append(pk)

                papers.append(paper_record_to_store_dict(p))
                if ingest_pause > 0 and i < len(new_papers) - 1:
                    await asyncio.sleep(ingest_pause)

            stats = corpus_metrics(tuple(store_dict_to_paper_record(d) for d in papers))
            current = await session_store.store.get(session_id)
            cur_out = dict(current.outcome or {})
            cur_out["papers"] = papers
            cur_out["corpus_stats"] = stats
            existing_vs = list(cur_out.get("visited_sources") or [])
            cur_out["visited_sources"] = existing_vs + new_source_keys
            prev_q = str(cur_out.get("arxiv_search_query") or "")
            suffix = f" · arXiv beam ({len(queries)} queries, +{len(new_papers)} papers)"
            cur_out["arxiv_search_query"] = (prev_q + suffix) if prev_q else f"{topic}{suffix}"
            await session_store.store.patch(session_id, outcome=cur_out)

            await asyncio.sleep(5)
            result = await _regenerate_knowledge_graph(
                b, topic, session_id, run_llm=True, existing_papers=papers
            )
            merged = _merge_regeneration_outcome(cur_out, result)
            await session_store.store.patch(session_id, status="ready", error=None, outcome=merged)
        except Exception as e:
            logger.exception("session %s extend-arxiv-beam failed", session_id)
            await session_store.store.patch(session_id, status="error", error=format_stored_session_error(e))

    background_tasks.add_task(_beam_job)

    return ArxivBeamExtendResponse(
        session_id=session_id,
        topic=topic,
        max_new_papers_requested=body.max_new_papers,
        status="processing",
    )


async def _regenerate_knowledge_graph(
    bridge,
    topic: str,
    session_id: str,
    run_llm: bool,
    existing_papers: list[dict[str, Any]],
) -> dict[str, Any]:
    from core.workflow import regenerate_session_knowledge_graph

    return await regenerate_session_knowledge_graph(
        bridge,
        topic=topic,
        session_id=session_id,
        run_llm=run_llm,
        existing_papers=existing_papers,
    )
