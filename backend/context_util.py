from __future__ import annotations

import logging
from typing import Any

from core.knowledge_graph_view import format_knowledge_graph_for_prompt

from .session_store import ResearchSessionRecord

logger = logging.getLogger(__name__)


def build_local_context(outcome: dict[str, Any], *, max_chars: int = 80_000) -> str:
    parts: list[str] = []
    fa = outcome.get("final_analysis")
    if isinstance(fa, str) and fa.strip():
        parts.append("## Prior synthesis\n" + fa.strip())
    uc = outcome.get("user_context")
    kc = outcome.get("knowledge_context")
    if isinstance(uc, str) and uc.strip():
        parts.append("## Gathered user context\n" + uc.strip()[:20_000])
    if isinstance(kc, str) and kc.strip():
        parts.append("## Gathered knowledge context\n" + kc.strip()[:20_000])
    kg_text = format_knowledge_graph_for_prompt(outcome.get("knowledge_graph"))
    if kg_text:
        parts.append(kg_text)
    parts.append("## Corpus item summaries")
    for p in (outcome.get("papers") or [])[:60]:
        if not isinstance(p, dict):
            continue
        title = str(p.get("title") or "")
        summary = str(p.get("summary") or "")[:4000]
        parts.append(f"### {title}\n{summary}")
    text = "\n\n".join(parts)
    return text[:max_chars]


async def session_retrieval_context(
    rec: ResearchSessionRecord,
    session_id: str,
    query: str,
) -> tuple[str, str]:
    """Return ``(context_text, source_tag)`` for Hydra recall or local corpus."""
    if rec.outcome is None:
        return "", "empty"
    context = ""
    source = "local_corpus"
    if rec.hydra_connected:
        try:
            from core.hydra_research_bridge import HydraResearchBridge

            bridge = HydraResearchBridge()
            ctx = await bridge.gather_context_for_topic(
                query,
                metadata_filters={"session_id": session_id},
            )
            u = (ctx.get("user_context") or "").strip()
            k = (ctx.get("knowledge_context") or "").strip()
            context = "\n\n".join(x for x in (u, k) if x)
            kg_text = format_knowledge_graph_for_prompt(rec.outcome.get("knowledge_graph"))
            if kg_text:
                context = f"{context}\n\n{kg_text}" if context else kg_text
            source = "hydra_recall"
        except Exception as e:
            logger.warning("Hydra recall failed; using local corpus: %s", e)
            context = build_local_context(rec.outcome)
            source = "local_fallback"
    else:
        context = build_local_context(rec.outcome)
    return context, source
