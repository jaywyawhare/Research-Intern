from __future__ import annotations

from .schemas import ResearchRunRequest, SessionCreateRequest


def corpus_maxima(body: ResearchRunRequest | SessionCreateRequest) -> tuple[int, int, int, int, int, int]:
    wiki = 0 if body.arxiv_only else body.wikipedia_max
    xref = 0 if body.arxiv_only else body.crossref_max
    epm = 0 if body.arxiv_only else body.europepmc_max
    pm = 0 if body.arxiv_only else body.pubmed_max
    oa = 0 if body.arxiv_only else body.openalex_max
    s2 = 0 if body.arxiv_only else body.semantic_scholar_max
    return wiki, xref, epm, pm, oa, s2
