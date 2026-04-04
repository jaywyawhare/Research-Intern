from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from core.workflow import run_literature_phase

from ..hydra_util import hydra_bridge_or_error
from ..params import corpus_maxima
from ..schemas import ResearchRunRequest, ResearchRunResponse, outcome_to_response

router = APIRouter(tags=["research"])


@router.post("/v1/research/run", response_model=ResearchRunResponse)
async def research_run(body: ResearchRunRequest) -> ResearchRunResponse:
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic must not be empty")

    session_id = (body.session_id or "").strip() or f"api_{uuid.uuid4().hex[:16]}"

    wiki_max, xref_max, epm_max, pm_max, oa_max, s2_max = corpus_maxima(body)

    bridge = hydra_bridge_or_error(body.use_hydra)

    llm_complete = not body.prompt_only
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
            llm_complete=llm_complete,
            llm_stream=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return outcome_to_response(
        outcome,
        include_analysis_prompt=body.include_analysis_prompt,
        include_papers=body.include_papers,
    )
