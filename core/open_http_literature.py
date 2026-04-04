from __future__ import annotations

import asyncio
import logging
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import certifi
import httpx

from .arxiv_literature import PaperRecord

logger = logging.getLogger(__name__)

_WIKI_UA = "ResearchIntern/1.0 (+https://arxiv.org/help/api; contact: local use)"
_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _crossref_mailto() -> str:
    return (
        os.environ.get("RESEARCH_INTERN_CROSSREF_MAILTO", "").strip()
        or "research-intern@users.noreply.github.org"
    )


def _ncbi_tool_email() -> tuple[str, str]:
    tool = os.environ.get("RESEARCH_INTERN_NCBI_TOOL", "").strip() or "research_intern"
    email = os.environ.get("RESEARCH_INTERN_NCBI_EMAIL", "").strip() or _crossref_mailto()
    return tool, email


def _openalex_user_agent() -> str:
    return f"ResearchIntern/1.0 (mailto:{_crossref_mailto()})"


def _reconstruct_openalex_abstract(inv: dict[str, Any] | None) -> str:
    if not inv or not isinstance(inv, dict):
        return ""
    pairs: list[tuple[int, str]] = []
    for word, positions in inv.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                pairs.append((pos, str(word)))
    pairs.sort(key=lambda x: x[0])
    return " ".join(w for _, w in pairs).strip()


def _xml_local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _wiki_path_segment(title: str) -> str:
    return urllib.parse.quote(title.replace(" ", "_"), safe="/()%!-_.~':")


def _strip_jats_like_abstract(raw: str) -> str:
    if not raw:
        return ""
    t = re.sub(r"<[^>]+>", " ", raw)
    return " ".join(t.split()).strip()


async def fetch_wikipedia_records(
    topic: str,
    *,
    max_results: int,
    client: httpx.AsyncClient,
) -> tuple[PaperRecord, ...]:
    if max_results <= 0 or not topic.strip():
        return ()
    limit = max(1, min(max_results, 8))
    params = {
        "action": "opensearch",
        "search": topic.strip(),
        "limit": str(limit),
        "namespace": "0",
        "format": "json",
    }
    try:
        r = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params=params,
            headers={"User-Agent": _WIKI_UA},
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Wikipedia opensearch failed: %s", e)
        return ()
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
        return ()
    titles: list[str] = data[1][:max_results]
    out: list[PaperRecord] = []
    for title in titles:
        path = _wiki_path_segment(title)
        su = f"https://en.wikipedia.org/api/rest_v1/page/summary/{path}"
        try:
            sr = await client.get(su, headers={"User-Agent": _WIKI_UA})
            if sr.status_code != 200:
                continue
            j = sr.json()
            extract = (j.get("extract") or "").strip()
            if not extract:
                continue
            disp = (j.get("title") or title).strip()
            urls = j.get("content_urls") or {}
            desktop = urls.get("desktop") or {}
            page_url = (desktop.get("page") or f"https://en.wikipedia.org/wiki/{path}").strip()
            ts = j.get("timestamp")
            pub = (str(ts)[:10] if ts else "") or ""
            out.append(
                PaperRecord(
                    arxiv_id=f"wiki:{disp}",
                    title=disp,
                    summary=extract,
                    published=pub,
                    abs_url=page_url,
                    source="wikipedia",
                )
            )
        except (httpx.HTTPError, ValueError, TypeError) as e:
            logger.debug("Wikipedia summary skip %r: %s", title, e)
            continue
    return tuple(out)


async def fetch_crossref_records(
    topic: str,
    *,
    max_results: int,
    client: httpx.AsyncClient,
    mailto: str | None = None,
) -> tuple[PaperRecord, ...]:
    if max_results <= 0 or not topic.strip():
        return ()
    rows = min(max(max_results, 1), 25)
    mail = mailto or _crossref_mailto()
    ua = f"ResearchIntern/1.0 (mailto:{mail})"
    params = {"query": topic.strip(), "rows": str(rows)}
    try:
        r = await client.get(
            "https://api.crossref.org/works",
            params=params,
            headers={"User-Agent": ua, "Accept": "application/json"},
        )
        r.raise_for_status()
        payload = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Crossref works search failed: %s", e)
        return ()
    items: list[dict[str, Any]] = (payload.get("message") or {}).get("items") or []
    out: list[PaperRecord] = []
    for it in items[:max_results]:
        titles = it.get("title") or []
        title = " ".join(titles) if isinstance(titles, list) and titles else ""
        if not title:
            continue
        doi = (it.get("DOI") or "").strip()
        abstract_raw = it.get("abstract")
        abstract = _strip_jats_like_abstract(abstract_raw) if isinstance(abstract_raw, str) else ""
        if not abstract:
            subs = it.get("subtitle") or []
            if isinstance(subs, list) and subs:
                abstract = " ".join(subs).strip()
        if not abstract:
            abstract = "(Crossref record has no abstract text.)"
        pub = ""
        for key in ("published-print", "published-online", "created", "issued"):
            dp = it.get(key)
            if isinstance(dp, dict) and dp.get("date-parts"):
                parts = dp["date-parts"][0]
                if isinstance(parts, list) and parts:
                    pub = "-".join(str(x) for x in parts[:3])[:10]
                    break
        url = f"https://doi.org/{doi}" if doi else f"https://search.crossref.org/?q={urllib.parse.quote(title)}"
        out.append(
            PaperRecord(
                arxiv_id=doi or title[:120],
                title=title,
                summary=abstract,
                published=pub,
                abs_url=url,
                source="crossref",
            )
        )
    return tuple(out)


async def fetch_europepmc_records(
    topic: str,
    *,
    max_results: int,
    client: httpx.AsyncClient,
) -> tuple[PaperRecord, ...]:
    if max_results <= 0 or not topic.strip():
        return ()
    size = min(max(max_results, 1), 25)
    params = {
        "query": topic.strip(),
        "format": "json",
        "pageSize": str(size),
        "resultType": "core",
    }
    try:
        r = await client.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params=params,
            headers={"User-Agent": _WIKI_UA},
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Europe PMC search failed: %s", e)
        return ()
    hits = (data.get("resultList") or {}).get("result") or []
    if not isinstance(hits, list):
        return ()
    out: list[PaperRecord] = []
    for hit in hits[:max_results]:
        if not isinstance(hit, dict):
            continue
        title = (hit.get("title") or "").strip()
        if not title:
            continue
        abst = (hit.get("abstractText") or "").strip() or "(no abstract in Europe PMC record.)"
        doi = (hit.get("doi") or "").strip()
        pmid = (hit.get("pmid") or "").strip()
        pmcid = (hit.get("pmcid") or "").strip()
        pid = doi or pmid or pmcid or (hit.get("id") or "")[:32]
        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://europepmc.org/article/MED/{pmid}"
        elif pmcid:
            url = f"https://europepmc.org/article/PMC/{pmcid}"
        else:
            url = "https://europepmc.org/"
        pub = (hit.get("firstPublicationDate") or hit.get("pubYear") or "")[:10]
        out.append(
            PaperRecord(
                arxiv_id=str(pid)[:120],
                title=title,
                summary=abst,
                published=pub,
                abs_url=url,
                source="europepmc",
            )
        )
    return tuple(out)


_SEMANTIC_SCHOLAR_DELAY_SEC = 1.05


async def fetch_openalex_records(
    topic: str,
    *,
    max_results: int,
    client: httpx.AsyncClient,
) -> tuple[PaperRecord, ...]:
    if max_results <= 0 or not topic.strip():
        return ()
    n = min(max(max_results, 1), 25)
    params = {"search": topic.strip(), "per_page": str(n)}
    try:
        r = await client.get(
            "https://api.openalex.org/works",
            params=params,
            headers={"User-Agent": _openalex_user_agent()},
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("OpenAlex works search failed: %s", e)
        return ()
    results = data.get("results") or []
    if not isinstance(results, list):
        return ()
    out: list[PaperRecord] = []
    for work in results[:max_results]:
        if not isinstance(work, dict):
            continue
        title = (work.get("title") or "").strip()
        if not title:
            continue
        wid = (work.get("id") or "").rstrip("/").split("/")[-1]
        if not wid:
            continue
        abstract = _reconstruct_openalex_abstract(work.get("abstract_inverted_index"))
        if not abstract:
            abstract = "(OpenAlex has no inverted-index abstract for this work.)"
        authors: list[str] = []
        for ash in work.get("authorships") or []:
            if not isinstance(ash, dict):
                continue
            auth = ash.get("author") or {}
            name = (auth.get("display_name") or "").strip()
            if name:
                authors.append(name)
        venue = ""
        pl = work.get("primary_location") or {}
        if isinstance(pl, dict):
            src = pl.get("source") or {}
            if isinstance(src, dict):
                venue = (src.get("display_name") or "").strip()
        if not venue:
            hv = work.get("host_venue") or {}
            if isinstance(hv, dict):
                venue = (hv.get("display_name") or "").strip()
        year = work.get("publication_year")
        pub = str(year) if year is not None else ""
        cites = int(work.get("cited_by_count") or 0)
        url = (work.get("id") or "").strip() or f"https://openalex.org/{wid}"
        out.append(
            PaperRecord(
                arxiv_id=f"openalex:{wid}",
                title=title,
                summary=abstract,
                published=pub,
                abs_url=url,
                source="openalex",
                authors=tuple(authors[:30]),
                venue=venue[:500],
                citation_count=cites,
            )
        )
    return tuple(out)


async def fetch_semantic_scholar_records(
    topic: str,
    *,
    max_results: int,
    client: httpx.AsyncClient,
) -> tuple[PaperRecord, ...]:
    if max_results <= 0 or not topic.strip():
        return ()
    lim = min(max(max_results, 1), 10)
    params = {
        "query": topic.strip(),
        "limit": str(lim),
        "fields": "paperId,title,abstract,year,authors,citationCount,venue,externalIds",
    }
    headers = {"User-Agent": _openalex_user_agent()}
    key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if key:
        headers["x-api-key"] = key
    try:
        r = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params=params,
            headers=headers,
        )
        if r.status_code == 429:
            logger.warning(
                "Semantic Scholar returned 429; reduce --semantic-scholar-max or set SEMANTIC_SCHOLAR_API_KEY",
            )
            return ()
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Semantic Scholar search failed: %s", e)
        return ()
    finally:
        await asyncio.sleep(_SEMANTIC_SCHOLAR_DELAY_SEC)

    papers = data.get("data") or []
    if not isinstance(papers, list):
        return ()
    out: list[PaperRecord] = []
    for paper in papers[:max_results]:
        if not isinstance(paper, dict):
            continue
        pid = (paper.get("paperId") or "").strip()
        title = (paper.get("title") or "").strip()
        if not pid or not title:
            continue
        auth_names: list[str] = []
        for au in paper.get("authors") or []:
            if isinstance(au, dict) and (au.get("name") or "").strip():
                auth_names.append((au.get("name") or "").strip())
        abst = (paper.get("abstract") or "").strip() or "(Semantic Scholar has no abstract for this paper.)"
        year = paper.get("year")
        pub = str(year) if year is not None else ""
        cites = int(paper.get("citationCount") or 0)
        venue = ((paper.get("venue") or "") or "").strip()[:500]
        url = f"https://www.semanticscholar.org/paper/{pid}"
        out.append(
            PaperRecord(
                arxiv_id=f"s2:{pid}",
                title=title,
                summary=abst,
                published=pub,
                abs_url=url,
                source="semantic_scholar",
                authors=tuple(auth_names[:30]),
                venue=venue,
                citation_count=cites,
            )
        )
    return tuple(out)


def _parse_pubmed_efetch_xml(raw: bytes) -> list[PaperRecord]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        logger.warning("PubMed efetch XML parse error: %s", e)
        return []
    out: list[PaperRecord] = []
    for node in root.iter():
        if _xml_local(node.tag) != "PubmedArticle":
            continue
        pmid = ""
        title = ""
        abstract_bits: list[str] = []
        year = ""
        for el in node.iter():
            loc = _xml_local(el.tag)
            if loc == "PMID" and el.text and not pmid:
                pmid = el.text.strip()
            elif loc == "ArticleTitle":
                title = " ".join(el.itertext()).strip()
            elif loc == "AbstractText":
                label = el.get("Label") or ""
                chunk = " ".join(el.itertext()).strip()
                if chunk:
                    abstract_bits.append(f"{label}: {chunk}" if label else chunk)
            elif loc == "Year" and el.text and not year:
                year = el.text.strip()[:4]
        if not pmid or not title:
            continue
        summary = "\n\n".join(abstract_bits) if abstract_bits else "(no abstract in PubMed record.)"
        pub = year or ""
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        out.append(
            PaperRecord(
                arxiv_id=f"pubmed:{pmid}",
                title=title,
                summary=summary,
                published=pub,
                abs_url=url,
                source="pubmed",
            )
        )
    return out


async def fetch_pubmed_records(
    topic: str,
    *,
    max_results: int,
    client: httpx.AsyncClient,
) -> tuple[PaperRecord, ...]:
    if max_results <= 0 or not topic.strip():
        return ()
    retmax = min(max(max_results, 1), 25)
    tool, email = _ncbi_tool_email()
    search_params = {
        "db": "pubmed",
        "term": topic.strip(),
        "retmax": str(retmax),
        "retmode": "json",
        "tool": tool,
        "email": email,
    }
    try:
        sr = await client.get(f"{_EUTILS}/esearch.fcgi", params=search_params)
        sr.raise_for_status()
        data = sr.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("PubMed esearch failed: %s", e)
        return ()
    idlist = (data.get("esearchresult") or {}).get("idlist") or []
    if not isinstance(idlist, list) or not idlist:
        return ()
    ids = ",".join(str(x) for x in idlist[:retmax])
    fetch_params = {
        "db": "pubmed",
        "id": ids,
        "retmode": "xml",
        "tool": tool,
        "email": email,
    }
    try:
        fr = await client.get(f"{_EUTILS}/efetch.fcgi", params=fetch_params)
        fr.raise_for_status()
        records = _parse_pubmed_efetch_xml(fr.content)
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("PubMed efetch failed: %s", e)
        return ()
    return tuple(records[:max_results])


def shared_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(60.0),
        verify=certifi.where(),
        follow_redirects=True,
    )
