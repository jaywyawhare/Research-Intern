from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from starlette.responses import StreamingResponse

from core.workflow import run_literature_phase

from ..agents.orchestrator import run_multi_agent_turn
from ..context_util import session_retrieval_context
from ..hydra_util import try_hydra_bridge
from ..params import corpus_maxima
from ..schemas import (
    MultiAgentTurnRequest,
    MultiAgentTurnResponse,
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
from ..session_store import ResearchSessionRecord, store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


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
    await store.patch(session_id, status="running", error=None)
    bridge = try_hydra_bridge(body.use_hydra)
    await store.patch(session_id, hydra_connected=bridge is not None)
    try:
        outcome = await run_literature_phase(
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
        )
        blob = literature_outcome_to_store(outcome)
        await store.patch(session_id, status="ready", outcome=blob, error=None)
    except Exception as e:
        logger.exception("session %s failed", session_id)
        await store.patch(session_id, status="error", error=str(e))


@router.post("/", response_model=SessionCreatedResponse)
async def create_session(
    body: SessionCreateRequest,
    background_tasks: BackgroundTasks,
) -> SessionCreatedResponse:
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic must not be empty")
    rec = await store.create(topic, use_hydra=body.use_hydra)
    background_tasks.add_task(_run_session_job, rec.session_id, body)
    return SessionCreatedResponse(
        session_id=rec.session_id,
        status=rec.status,
        topic=rec.topic,
        use_hydra=rec.use_hydra,
    )


@router.get("/", response_model=list[SessionSummary])
async def list_sessions() -> list[SessionSummary]:
    rows = await store.list_summaries()
    return [_summary(r) for r in rows]


@router.get("/{session_id}/events")
async def session_status_events(session_id: str) -> StreamingResponse:
    """Server-Sent Events: periodic ``status`` until ``ready`` or ``error`` (or unknown session)."""

    async def gen():
        while True:
            rec = await store.get(session_id)
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
    rec = await store.get(session_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="session not found")
    outcome_resp = None
    if rec.status == "ready" and rec.outcome is not None:
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


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    ok = await store.delete(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")


@router.post("/{session_id}/agents/turn", response_model=MultiAgentTurnResponse)
async def multi_agent_turn(session_id: str, body: MultiAgentTurnRequest) -> MultiAgentTurnResponse:
    rec = await store.get(session_id)
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
    rec = await store.get(session_id)
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
