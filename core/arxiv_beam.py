from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any

import httpx

from .arxiv_literature import (
    PaperRecord,
    build_arxiv_search_query,
    fetch_recent_papers,
)

_TITLE_STOP = frozenset(
    """
    a an the and or for of in on to with via from by as at is are was were be been being
    our we their its this that these those it we you they he she
    """.split()
)


def paper_record_to_store_dict(p: PaperRecord) -> dict[str, Any]:
    """Shape stored in session ``outcome["papers"]``."""
    return {
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


def store_dict_to_paper_record(d: dict[str, Any]) -> PaperRecord:
    au = d.get("authors") or []
    return PaperRecord(
        arxiv_id=str(d.get("arxiv_id", "")),
        title=str(d.get("title", "")),
        summary=str(d.get("summary", "")),
        published=str(d.get("published", "")),
        abs_url=str(d.get("abs_url", "")),
        source=str(d.get("source", "arxiv")),
        authors=tuple(au) if isinstance(au, list) else (),
        venue=str(d.get("venue", "")),
        citation_count=int(d.get("citation_count", 0) or 0),
    )


def _title_to_topic_phrase(title: str, *, max_words: int = 5) -> str | None:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9+.-]*", title or "")
    kept: list[str] = []
    for w in words:
        wl = w.lower()
        if len(w) < 2 or wl in _TITLE_STOP:
            continue
        kept.append(w)
        if len(kept) >= max_words:
            break
    if len(kept) < 2:
        return None
    return " ".join(kept)


async def arxiv_beam_expand(
    topic: str,
    *,
    existing_arxiv_ids: set[str],
    visited_sources: set[str] | None = None,
    beam_width: int = 5,
    depth: int = 2,
    max_new_papers: int = 20,
    restrict_cs_stat_ml: bool = True,
    raw_arxiv_query: bool = False,
    client: httpx.AsyncClient | None = None,
) -> tuple[tuple[PaperRecord, ...], list[str]]:
    """
    Expand the corpus by querying arXiv in waves:

    - Wave 0: phrase search from ``topic`` (same rules as ``build_arxiv_search_query``).
    - Later waves: up to ``beam_width`` distinct phrase queries built from the titles of
      papers discovered in the previous wave (first meaningful words, stopword-stripped).

    Stops when ``depth`` waves are done, ``max_new_papers`` new ids are collected, or
    no new papers appear. Dedupes against ``existing_arxiv_ids`` and within the run.
    """
    topic = (topic or "").strip()
    if not topic:
        return (), []

    bw = max(1, min(beam_width, 25))
    dep = max(1, min(depth, 5))
    cap = max(1, min(max_new_papers, 100))

    seen: set[str] = set(existing_arxiv_ids)
    source_keys: set[str] = set(visited_sources or set())
    collected: list[PaperRecord] = []
    queries_tried: list[str] = []
    tried_q: set[str] = set()

    async def fetch_query(q: str, max_results: int) -> list[PaperRecord]:
        if not (q or "").strip():
            return []
        if q in tried_q:
            return []
        tried_q.add(q)
        queries_tried.append(q)
        res = await fetch_recent_papers(
            q,
            max_results=max_results,
            restrict_cs_stat_ml=restrict_cs_stat_ml,
            raw_arxiv_query=raw_arxiv_query,
            client=client,
        )
        out: list[PaperRecord] = []
        for p in res.papers:
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
            t = re.sub(r'[^a-z0-9\s]', '', p.title.lower().strip())
            t = re.sub(r'\s+', ' ', t)
            if t:
                h = hashlib.md5(t.encode()).hexdigest()[:12]
                keys.append(f'title:{h}')
            if not keys:
                keys.append(f'unknown:{p.abs_url or p.source}')

            if any(k in source_keys for k in keys) or p.arxiv_id in seen:
                continue
            seen.add(p.arxiv_id)
            source_keys.update(keys)
            out.append(p)
            if len(collected) + len(out) >= cap:
                break
        return out

    async def polite_pause() -> None:
        await asyncio.sleep(0.35)

    # Wave 0: session topic
    q0 = build_arxiv_search_query(
        topic,
        restrict_cs_stat_ml=restrict_cs_stat_ml,
        raw_arxiv_query=raw_arxiv_query,
    )
    batch = await fetch_query(q0, max(bw, 5))
    collected.extend(batch)
    frontier = batch[:bw]

    for _wave in range(1, dep):
        if len(collected) >= cap or not frontier:
            break
        subqs: list[str] = []
        for p in frontier:
            phrase = _title_to_topic_phrase(p.title)
            if not phrase:
                continue
            sq = build_arxiv_search_query(
                phrase,
                restrict_cs_stat_ml=restrict_cs_stat_ml,
                raw_arxiv_query=False,
            )
            if sq not in tried_q and sq != q0:
                subqs.append(sq)
            if len(subqs) >= bw:
                break
        if not subqs:
            break
        next_frontier: list[PaperRecord] = []
        for sq in subqs[:bw]:
            if len(collected) >= cap:
                break
            b = await fetch_query(sq, bw)
            collected.extend(b)
            next_frontier.extend(b)
            await polite_pause()
        frontier = next_frontier[:bw]
        if not next_frontier:
            break

    return tuple(collected[:cap]), queries_tried
