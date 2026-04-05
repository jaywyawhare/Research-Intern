from __future__ import annotations

import json
import logging
import re
from typing import Any

from core.llm_completion import run_analysis_completion

logger = logging.getLogger(__name__)

_VALID = frozenset({"librarian", "scholar", "interlocutor"})


def _tail_transcript(transcript: list[dict[str, Any]], max_turns: int = 6) -> str:
    lines: list[str] = []
    for row in transcript[-max_turns:]:
        role = row.get("role", "")
        agent = row.get("agent")
        content = (row.get("content") or "")[:2000]
        tag = f"{role}" + (f"/{agent}" if agent else "")
        lines.append(f"[{tag}] {content}")
    return "\n".join(lines) if lines else "(no prior turns)"


def _route_heuristic(message: str) -> tuple[list[str], str]:
    m = message.lower()
    if any(
        w in m
        for w in (
            "summarize",
            "overview",
            "themes",
            "synthesis",
            "landscape",
            "trends",
            "methodolog",
        )
    ):
        return ["scholar"], "heuristic: synthesis-style request"
    if any(
        w in m
        for w in (
            "what papers",
            "which sources",
            "corpus",
            "how many",
            "coverage",
            "do we have",
            "ingested",
        )
    ):
        return ["librarian"], "heuristic: corpus inventory"
    return ["interlocutor"], "heuristic: default Q&A"


def _parse_router_json(raw: str) -> tuple[list[str], str] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    agents = data.get("agents") or data.get("pipeline")
    if not isinstance(agents, list):
        return None
    out: list[str] = []
    for a in agents:
        if isinstance(a, str) and a.strip().lower() in _VALID:
            aid = a.strip().lower()
            if aid not in out:
                out.append(aid)
    if not out:
        return None
    rationale = data.get("rationale") if isinstance(data.get("rationale"), str) else ""
    return out[:3], rationale or ""


async def plan_agent_pipeline(
    *,
    topic: str,
    user_message: str,
    transcript: list[dict[str, Any]],
    force_agents: list[str] | None,
) -> tuple[list[str], str | None]:
    if force_agents:
        out: list[str] = []
        for a in force_agents:
            aid = a.strip().lower()
            if aid in _VALID and aid not in out:
                out.append(aid)
        return (out[:3] if out else ["interlocutor"], "client forced agent order")

    try:
        tail = _tail_transcript(transcript)
        prompt = (
            "You route user messages to specialist agents for a research session.\n\n"
            "Agents (use lowercase ids only):\n"
            "- librarian: corpus inventory (counts, sources, gaps, what was gathered).\n"
            "- scholar: thematic synthesis (trends, methods, big-picture narrative across papers).\n"
            "- interlocutor: targeted Q&A (specific factual or analytical questions).\n\n"
            "Rules:\n"
            "- Return JSON only, no markdown.\n"
            '- Shape: {"agents":["interlocutor"],"rationale":"one short sentence"}\n'
            "- Use one agent unless the user clearly needs two steps (e.g. librarian then interlocutor).\n"
            "- At most 3 agents in `agents`.\n\n"
            f"Session topic: {topic!r}\n"
            f"Recent transcript:\n{tail}\n\n"
            f"User message: {user_message!r}\n"
        )
        raw = await run_analysis_completion(prompt, stream=False, temperature=0.1)
        parsed = _parse_router_json(raw)
        if parsed:
            return parsed
    except (ValueError, RuntimeError, OSError) as e:
        logger.info("LLM router unavailable, using heuristics: %s", e)

    agents, why = _route_heuristic(user_message)
    return agents, why
