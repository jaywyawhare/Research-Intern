from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.arxiv_literature import PaperRecord
from core.workflow import LiteraturePhaseOutcome


def literature_outcome_to_store(o: LiteraturePhaseOutcome) -> dict[str, Any]:
    return {
        "topic": o.topic,
        "session_id": o.session_id,
        "arxiv_search_query": o.arxiv_search_query,
        "extra_source_summary": o.extra_source_summary,
        "corpus_stats": o.corpus_stats,
        "user_context": o.user_context,
        "knowledge_context": o.knowledge_context,
        "analysis_prompt": o.analysis_prompt,
        "final_analysis": o.final_analysis,
        "knowledge_graph": o.knowledge_graph,
        "visited_sources": o.visited_sources or [],
        "synthesis_history": [],
        "papers": [
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "summary": p.summary,
                "published": p.published,
                "abs_url": p.abs_url,
                "source": p.source,
                "authors": list(p.authors),
                "venue": p.venue,
                "citation_count": p.citation_count,
            }
            for p in o.papers
        ],
    }


class SynthesisHistoryEntry(BaseModel):
    """Older synthesis runs after regenerate (newest previous first)."""

    ts: float
    text: str


class PaperOut(BaseModel):
    arxiv_id: str
    title: str
    summary: str
    published: str
    abs_url: str
    source: str = "arxiv"
    authors: list[str] = Field(default_factory=list)
    venue: str = ""
    citation_count: int = 0


class ResearchRunRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="Research topic or raw arXiv query when raw_arxiv_query is true.")
    session_id: str | None = Field(
        default=None,
        description="Stable id for Hydra ingest/recall; server generates one if omitted.",
    )
    use_hydra: bool = True
    ingest_to_knowledge: bool = True
    max_papers: int = Field(default=30, ge=1, le=200)
    restrict_arxiv_cs_stat_ml: bool = True
    raw_arxiv_query: bool = False
    restrict_recall_to_session: bool = False
    ingest_pause_seconds: float = Field(default=0.6, ge=0.0, le=60.0)
    wikipedia_max: int = Field(default=2, ge=0, le=50)
    crossref_max: int = Field(default=4, ge=0, le=50)
    europepmc_max: int = Field(default=0, ge=0, le=50)
    pubmed_max: int = Field(default=0, ge=0, le=50)
    openalex_max: int = Field(default=0, ge=0, le=50)
    semantic_scholar_max: int = Field(default=0, ge=0, le=50)
    arxiv_only: bool = False
    crossref_mailto: str | None = None
    recall_metadata_filters: dict[str, Any] | None = None
    prompt_only: bool = Field(
        default=False,
        description="If true, skip LLM; final_analysis will be null and only the prompt is produced.",
    )
    include_analysis_prompt: bool = Field(
        default=True,
        description="If false, analysis_prompt is omitted from the JSON (smaller payloads).",
    )
    include_papers: bool = Field(
        default=True,
        description="If false, papers list is omitted; corpus_stats still returns counts.",
    )


class ResearchRunResponse(BaseModel):
    topic: str
    session_id: str
    arxiv_search_query: str
    extra_source_summary: str
    corpus_stats: dict[str, Any]
    user_context: str
    knowledge_context: str
    analysis_prompt: str | None = None
    final_analysis: str | None = None
    knowledge_graph: dict[str, Any] | None = None
    synthesis_history: list[SynthesisHistoryEntry] = Field(
        default_factory=list,
        description="Prior syntheses after re-run (newest previous first).",
    )
    synthesis_error: str | None = Field(
        default=None,
        description="Last LLM error during regeneration, if any (cleared on success).",
    )
    papers: list[PaperOut] | None = None
    visited_sources: list[str] = Field(
        default_factory=list,
        description="Canonical dedup keys for all fetched sources (DOI, arXiv ID, or title hash).",
    )


def stored_outcome_to_response(
    d: dict[str, Any],
    *,
    include_analysis_prompt: bool,
    include_papers: bool,
) -> ResearchRunResponse:
    papers: list[PaperOut] | None = None
    if include_papers:
        papers = [PaperOut.model_validate(p) for p in d.get("papers") or []]
    hist_raw = d.get("synthesis_history") or []
    synthesis_history: list[SynthesisHistoryEntry] = []
    for item in hist_raw:
        if isinstance(item, dict) and "ts" in item and "text" in item:
            try:
                synthesis_history.append(
                    SynthesisHistoryEntry(ts=float(item["ts"]), text=str(item["text"]))
                )
            except (TypeError, ValueError):
                continue

    return ResearchRunResponse(
        topic=d["topic"],
        session_id=d["session_id"],
        arxiv_search_query=d["arxiv_search_query"],
        extra_source_summary=d.get("extra_source_summary") or "",
        corpus_stats=d.get("corpus_stats") or {},
        user_context=d.get("user_context") or "",
        knowledge_context=d.get("knowledge_context") or "",
        analysis_prompt=d.get("analysis_prompt") if include_analysis_prompt else None,
        final_analysis=d.get("final_analysis"),
        knowledge_graph=d.get("knowledge_graph"),
        synthesis_history=synthesis_history,
        synthesis_error=d.get("synthesis_error"),
        papers=papers,
        visited_sources=d.get("visited_sources") or [],
    )


class SessionCreateRequest(BaseModel):
    """Start a durable research session (corpus + optional Hydra ingest scoped to ``session_id``)."""

    topic: str = Field(..., min_length=1)
    use_hydra: bool = True
    ingest_to_knowledge: bool = True
    max_papers: int = Field(default=30, ge=1, le=200)
    restrict_arxiv_cs_stat_ml: bool = True
    raw_arxiv_query: bool = False
    restrict_recall_to_session: bool = Field(
        default=True,
        description="Recall/ingest scoped to this session so multiple topics stay isolated.",
    )
    ingest_pause_seconds: float = Field(default=0.6, ge=0.0, le=60.0)
    wikipedia_max: int = Field(default=2, ge=0, le=50)
    crossref_max: int = Field(default=4, ge=0, le=50)
    europepmc_max: int = Field(default=0, ge=0, le=50)
    pubmed_max: int = Field(default=0, ge=0, le=50)
    openalex_max: int = Field(default=0, ge=0, le=50)
    semantic_scholar_max: int = Field(default=0, ge=0, le=50)
    arxiv_only: bool = False
    crossref_mailto: str | None = None
    recall_metadata_filters: dict[str, Any] | None = None
    prompt_only: bool = Field(
        default=False,
        description="If true, skip the initial LLM synthesis (prompt still stored for later).",
    )


class SessionCreatedResponse(BaseModel):
    session_id: str
    status: str
    topic: str
    use_hydra: bool


class SessionSummary(BaseModel):
    session_id: str
    topic: str
    status: str
    created_at: float
    updated_at: float
    use_hydra: bool
    hydra_connected: bool
    error: str | None = None


class TranscriptTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    content: str
    ts: float
    agent: str | None = None


class SessionDetailResponse(SessionSummary):
    outcome: ResearchRunResponse | None = None
    transcript: list[TranscriptTurn] = Field(default_factory=list)


class MultiAgentTurnRequest(BaseModel):
    message: str = Field(..., min_length=1)
    force_agents: list[str] | None = Field(
        default=None,
        description="Optional lowercase pipeline, e.g. ['librarian','interlocutor']. Skips LLM router.",
    )
    run_auditor: bool = Field(
        default=False,
        description="If true, an auditor agent reviews the last specialist output against evidence.",
    )


class AgentInvocation(BaseModel):
    agent_id: str
    content: str
    context_source: str | None = None


class MultiAgentTurnResponse(BaseModel):
    agents_invoked: list[AgentInvocation]
    router_rationale: str | None = None
    final_answer: str


class SessionAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    answer_with_llm: bool = Field(
        default=True,
        description="If false, only returns retrieved_context (no OPENAI_API_KEY required).",
    )


class SessionAskResponse(BaseModel):
    answer: str | None = None
    retrieved_context: str
    context_source: str = Field(
        description="hydra_recall | local_corpus | local_fallback",
    )


class RegenerateGraphRequest(BaseModel):
    run_llm_analysis: bool = Field(
        default=True,
        description=(
            "Defaults to true: after refreshing recall/graph data, run LLM synthesis. "
            "Set to false only for a graph-only refresh (no API call, no final_analysis update)."
        ),
    )


class RegenerateGraphResponse(BaseModel):
    session_id: str
    topic: str
    knowledge_graph: dict[str, Any] | None = None
    status: str


class AddSourceRequest(BaseModel):
    title: str = Field(..., min_length=1)
    body_md: str = Field(..., min_length=1, description="Markdown content of the source.")
    source_url: str | None = Field(default=None)
    extra_metadata: dict[str, Any] | None = Field(default=None)


class AddSourceResponse(BaseModel):
    session_id: str
    source_title: str
    knowledge_graph: dict[str, Any] | None = None
    papers_count: int
    status: str = "processing"


class ArxivBeamExtendRequest(BaseModel):
    """Expand the session corpus via multi-query arXiv search (topic seed, then title-derived phrases)."""

    beam_width: int = Field(default=5, ge=1, le=25, description="Papers per query wave; caps title-derived queries.")
    depth: int = Field(default=2, ge=1, le=5, description="Number of waves (1 = topic query only).")
    max_new_papers: int = Field(default=20, ge=1, le=100)
    restrict_arxiv_cs_stat_ml: bool = Field(
        default=True,
        description="If true, limit arXiv results to cs.CL / cs.AI / cs.LG / stat.ML (same as initial session).",
    )
    raw_arxiv_query: bool = Field(
        default=False,
        description="If true, treat the session topic as a raw arXiv search_query string.",
    )


class ArxivBeamExtendResponse(BaseModel):
    session_id: str
    topic: str
    max_new_papers_requested: int
    status: str = "processing"


def _paper_out(p: PaperRecord) -> PaperOut:
    return PaperOut(
        arxiv_id=p.arxiv_id,
        title=p.title,
        summary=p.summary,
        published=p.published,
        abs_url=p.abs_url,
        source=p.source,
        authors=list(p.authors),
        venue=p.venue,
        citation_count=p.citation_count,
    )


def outcome_to_response(
    o: LiteraturePhaseOutcome,
    *,
    include_analysis_prompt: bool,
    include_papers: bool,
) -> ResearchRunResponse:
    papers: list[PaperOut] | None = None
    if include_papers:
        papers = [_paper_out(p) for p in o.papers]
    return ResearchRunResponse(
        topic=o.topic,
        session_id=o.session_id,
        arxiv_search_query=o.arxiv_search_query,
        extra_source_summary=o.extra_source_summary,
        corpus_stats=o.corpus_stats,
        user_context=o.user_context,
        knowledge_context=o.knowledge_context,
        analysis_prompt=o.analysis_prompt if include_analysis_prompt else None,
        final_analysis=o.final_analysis,
        knowledge_graph=o.knowledge_graph,
        synthesis_history=[],
        papers=papers,
    )
