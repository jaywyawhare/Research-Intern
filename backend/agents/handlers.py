from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from core.llm_completion import run_analysis_completion

from .types import AgentContext, AgentStepResult

logger = logging.getLogger(__name__)

Handler = Callable[[AgentContext], Awaitable[AgentStepResult]]


async def run_librarian(ctx: AgentContext) -> AgentStepResult:
    outcome = ctx.outcome
    stats = outcome.get("corpus_stats") or {}
    extras = outcome.get("extra_source_summary") or ""
    arxiv_q = outcome.get("arxiv_search_query") or ""
    papers = outcome.get("papers") or []
    titles = [str(p.get("title", ""))[:120] for p in papers[:40] if isinstance(p, dict)]
    pack_obj: dict[str, Any] = {
        "arxiv_search_query": arxiv_q,
        "corpus_stats": stats,
        "extra_source_summary": extras,
        "sample_titles": titles,
        "paper_count": len(papers),
    }
    kg = outcome.get("knowledge_graph")
    if isinstance(kg, dict):
        kst = kg.get("stats") if isinstance(kg.get("stats"), dict) else {}
        if int(kst.get("edge_count", 0) or 0) > 0 or int(kst.get("node_count", 0) or 0) > 0:
            pack_obj["knowledge_graph"] = {
                "stats": kst,
                "relations": [
                    {
                        "source": str(e.get("source_label") or "")[:200],
                        "predicate": str(e.get("predicate") or "")[:160],
                        "target": str(e.get("target_label") or "")[:200],
                    }
                    for e in (kg.get("edges") or [])[:50]
                    if isinstance(e, dict)
                ],
            }
    pack = json.dumps(pack_obj, indent=2)[:25_000]
    try:
        prompt = (
            f'You are the **librarian** agent for a session on "{ctx.topic}".\n'
            f"The user asked: {ctx.user_message!r}\n\n"
            f"### Corpus snapshot (structured)\n{pack}\n\n"
            "### Full-text context (truncated)\n"
            f"{ctx.retrieved_context[:50_000]}\n\n"
            "Respond concisely: what sources exist, coverage, obvious gaps, and how it relates "
            "to the user's request."
        )
        text = await run_analysis_completion(prompt, stream=False, temperature=0.3)
    except (ValueError, RuntimeError) as e:
        logger.info("Librarian LLM skipped: %s", e)
        text = (
            f"**Corpus (no LLM)**\n- Query: {arxiv_q}\n- Stats: {stats}\n"
            f"- Papers: {len(papers)}\n- Extras:\n{extras}"
        )
    return AgentStepResult(
        agent_id="librarian",
        content=text.strip(),
        context_source=ctx.context_source,
        retrieved_context=ctx.retrieved_context,
    )


async def run_scholar(ctx: AgentContext) -> AgentStepResult:
    try:
        prompt = (
            f'You are the **scholar** agent synthesizing literature for "{ctx.topic}".\n'
            f"The user asked: {ctx.user_message!r}\n\n"
            "### Evidence\n"
            f"{ctx.retrieved_context[:70_000]}\n\n"
            "Produce a structured synthesis: themes, methods, disagreements, and open questions. "
            "If relevant, refine or extend **hypotheses** and **experiment proposals** (conceptual study "
            "design only; no code or execution). Ground claims in the evidence; flag uncertainty."
        )
        text = await run_analysis_completion(prompt, stream=False, temperature=0.4)
    except (ValueError, RuntimeError) as e:
        logger.info("Scholar LLM skipped: %s", e)
        text = (
            "LLM unavailable for thematic synthesis. "
            "Use `answer_with_llm` flows with API keys, or read `retrieved_context` from the prior step."
        )
    return AgentStepResult(
        agent_id="scholar",
        content=text.strip(),
        context_source=ctx.context_source,
        retrieved_context=ctx.retrieved_context,
    )


async def run_interlocutor(ctx: AgentContext) -> AgentStepResult:
    try:
        prompt = (
            f'You are the **interlocutor** agent for "{ctx.topic}".\n\n'
            "### Retrieved context\n"
            f"{ctx.retrieved_context[:70_000]}\n\n"
            f"### User\n{ctx.user_message}\n\n"
            "Answer directly from the context. If insufficient, say what is missing."
        )
        text = await run_analysis_completion(prompt, stream=False, temperature=0.3)
    except (ValueError, RuntimeError) as e:
        logger.info("Interlocutor LLM skipped: %s", e)
        text = (
            "[No LLM] Retrieved context is below; form your own answer.\n\n"
            + ctx.retrieved_context[:12_000]
        )
    return AgentStepResult(
        agent_id="interlocutor",
        content=text.strip(),
        context_source=ctx.context_source,
        retrieved_context=ctx.retrieved_context,
    )


async def run_auditor(ctx: AgentContext, draft_answer: str) -> AgentStepResult:
    try:
        prompt = (
            "You are the **auditor** agent. Check whether the draft answer is supported by the evidence.\n\n"
            "### Evidence (truncated)\n"
            f"{ctx.retrieved_context[:60_000]}\n\n"
            "### Draft answer\n"
            f"{draft_answer[:20_000]}\n\n"
            "### Original user request\n"
            f"{ctx.user_message!r}\n\n"
            "Reply briefly: verdict (supported / partial / unsupported) and concrete notes."
        )
        text = await run_analysis_completion(prompt, stream=False, temperature=0.2)
    except (ValueError, RuntimeError) as e:
        logger.info("Auditor LLM skipped: %s", e)
        text = f"[Auditor skipped: {e}]"
    return AgentStepResult(
        agent_id="auditor",
        content=text.strip(),
        context_source=ctx.context_source,
        retrieved_context=None,
    )


HANDLERS: dict[str, Handler] = {
    "librarian": run_librarian,
    "scholar": run_scholar,
    "interlocutor": run_interlocutor,
}
