from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import certifi
import httpx

_ATOM = "{http://www.w3.org/2005/Atom}"

_DEFAULT_ML_CS_STATS_CATS = "(cat:cs.CL OR cat:cs.AI OR cat:cs.LG OR cat:stat.ML)"


@dataclass(frozen=True)
class PaperRecord:
    """One text unit in the analysis corpus (arXiv preprint or keyless web source)."""

    arxiv_id: str
    title: str
    summary: str
    published: str
    abs_url: str
    source: str = "arxiv"
    authors: tuple[str, ...] = ()
    venue: str = ""
    citation_count: int = 0


@dataclass(frozen=True)
class ArxivFetchResult:
    papers: tuple[PaperRecord, ...]
    search_query: str


def _arxiv_id_from_entry_id(entry_id: str) -> str:
    """Extract raw id (e.g. 1706.03762v7) from an arXiv abs URL."""
    m = re.search(r"arxiv\.org/abs/([^?#]+)", entry_id, re.I)
    if m:
        return m.group(1).strip()
    return entry_id.rsplit("/", maxsplit=1)[-1].strip()


def build_arxiv_search_query(
    topic: str,
    *,
    restrict_cs_stat_ml: bool = True,
    raw_arxiv_query: bool = False,
) -> str:
    """
    Build an arXiv ``search_query`` string.

    - Normal topics are turned into a **phrase** query: ``all:"your topic"`` so words are not OR-matched
      loosely across unrelated papers.
    - With ``restrict_cs_stat_ml=True`` (default), results are limited to cs.CL / cs.AI / cs.LG / stat.ML.
    - With ``raw_arxiv_query=True``, ``topic`` is sent unchanged (for power users), e.g.
      ``(cat:astro-ph.EP) AND all:"exoplanet"``.
    """
    t = topic.strip()
    if not t:
        return ""
    if raw_arxiv_query:
        return t
    if re.match(r"^[a-z][a-z0-9._-]*\s*:", t, re.I) or t.startswith("("):
        return t
    inner = re.sub(r'["\\\\]', " ", t)
    inner = " ".join(inner.split())
    body = f'all:"{inner}"'
    if restrict_cs_stat_ml:
        body = f"{_DEFAULT_ML_CS_STATS_CATS} AND ({body})"
    return body


def _parse_arxiv_atom(raw: bytes) -> list[PaperRecord]:
    root = ET.fromstring(raw)
    papers: list[PaperRecord] = []
    for entry in root.findall(f"{_ATOM}entry"):
        title_el = entry.find(f"{_ATOM}title")
        summary_el = entry.find(f"{_ATOM}summary")
        id_el = entry.find(f"{_ATOM}id")
        published_el = entry.find(f"{_ATOM}published")
        if title_el is None or summary_el is None or id_el is None:
            continue
        title = " ".join((title_el.text or "").split())
        summary = (summary_el.text or "").strip()
        eid = (id_el.text or "").strip()
        published = (published_el.text or "")[:10] if published_el is not None else ""
        authors: list[str] = []
        for au in entry.findall(f"{_ATOM}author"):
            ne = au.find(f"{_ATOM}name")
            if ne is not None and (ne.text or "").strip():
                authors.append((ne.text or "").strip())
        papers.append(
            PaperRecord(
                arxiv_id=_arxiv_id_from_entry_id(eid),
                title=title,
                summary=summary,
                published=published,
                abs_url=eid if eid.startswith("http") else f"https://arxiv.org/abs/{eid}",
                source="arxiv",
                authors=tuple(authors),
            )
        )
    return papers


async def fetch_recent_papers(
    topic: str,
    *,
    max_results: int = 30,
    restrict_cs_stat_ml: bool = True,
    raw_arxiv_query: bool = False,
    client: httpx.AsyncClient | None = None,
) -> ArxivFetchResult:
    """
    Return recent arXiv papers (newest first) and the **exact** ``search_query`` sent to the API.

    Pass ``client`` to reuse TLS connections with other keyless fetches.
    """
    if not topic.strip():
        return ArxivFetchResult(papers=(), search_query="")
    n = max(1, min(max_results, 100))
    search_query = build_arxiv_search_query(
        topic,
        restrict_cs_stat_ml=restrict_cs_stat_ml,
        raw_arxiv_query=raw_arxiv_query,
    )
    encoded = urllib.parse.quote(search_query, safe="")
    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query={encoded}&start=0&max_results={n}"
        "&sortBy=submittedDate&sortOrder=descending"
    )
    headers = {"User-Agent": "ResearchIntern/1.0 (+https://arxiv.org/help/api)"}

    async def _do_get(c: httpx.AsyncClient) -> ArxivFetchResult:
        response = await c.get(url, headers=headers)
        response.raise_for_status()
        return ArxivFetchResult(papers=tuple(_parse_arxiv_atom(response.content)), search_query=search_query)

    if client is not None:
        return await _do_get(client)
    async with httpx.AsyncClient(
        timeout=60.0,
        verify=certifi.where(),
        follow_redirects=True,
    ) as c:
        return await _do_get(c)


def corpus_metrics(papers: tuple[PaperRecord, ...]) -> dict[str, Any]:
    """Counts by source and basic summary coverage (for dashboards or logging)."""
    by_source: dict[str, int] = {}
    for p in papers:
        by_source[p.source] = by_source.get(p.source, 0) + 1
    substantial = sum(1 for p in papers if len((p.summary or "").strip()) > 40)
    with_venue = sum(1 for p in papers if (p.venue or "").strip())
    with_authors = sum(1 for p in papers if p.authors)
    return {
        "total": len(papers),
        "by_source": by_source,
        "with_substantial_summary": substantial,
        "with_venue": with_venue,
        "with_authors": with_authors,
    }
