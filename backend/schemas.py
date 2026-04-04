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
    papers: list[PaperOut] | None = None


def stored_outcome_to_response(
    d: dict[str, Any],
    *,
    include_analysis_prompt: bool,
    include_papers: bool,
) -> ResearchRunResponse:
    papers: list[PaperOut] | None = None
    if include_papers:
        papers = [PaperOut.model_validate(p) for p in d.get("papers") or []]
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
        papers=papers,
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
        papers=papers,
    )
