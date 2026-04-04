from __future__ import annotations

import importlib
from typing import Any

from .arxiv_literature import (
    ArxivFetchResult,
    PaperRecord,
    build_arxiv_search_query,
    corpus_metrics,
    fetch_recent_papers,
)
from .context_builder import build_context_string
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
from .prompts import build_analysis_prompt, build_thinking_protocol_prompt
from .thinking_engine import (
    ThinkingEngine,
    ThinkingValidationError,
    normalize_thought_payload,
    persist_thought_to_hydra,
)
from .workflow import LiteraturePhaseOutcome, build_research_intern_analysis_prompt, run_literature_phase

__all__ = [
    "HydraResearchBridge",
    "run_analysis_completion",
    "build_analysis_prompt",
    "build_thinking_protocol_prompt",
    "build_context_string",
    "PaperRecord",
    "ArxivFetchResult",
    "build_arxiv_search_query",
    "fetch_recent_papers",
    "corpus_metrics",
    "fetch_crossref_records",
    "fetch_europepmc_records",
    "fetch_openalex_records",
    "fetch_pubmed_records",
    "fetch_semantic_scholar_records",
    "fetch_wikipedia_records",
    "shared_http_client",
    "LiteraturePhaseOutcome",
    "build_research_intern_analysis_prompt",
    "run_literature_phase",
    "ThinkingEngine",
    "ThinkingValidationError",
    "normalize_thought_payload",
    "persist_thought_to_hydra",
]


def __getattr__(name: str) -> Any:
    if name == "HydraResearchBridge":
        mod = importlib.import_module(f"{__name__}.hydra_research_bridge")
        return getattr(mod, "HydraResearchBridge")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
