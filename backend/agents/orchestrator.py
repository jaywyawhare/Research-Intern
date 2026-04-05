from __future__ import annotations

import time
from typing import Any

from ..context_util import session_retrieval_context
from ..schemas import AgentInvocation, MultiAgentTurnResponse
from .. import session_store
from ..session_store import ResearchSessionRecord
from .handlers import HANDLERS, run_auditor as auditor_agent
from .router import _tail_transcript, plan_agent_pipeline
from .types import AgentContext, AgentStepResult


def _transcript_entry(
    *,
    role: str,
    content: str,
    agent: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {"role": role, "content": content, "ts": time.time()}
    if agent:
        row["agent"] = agent
    return row


async def run_multi_agent_turn(
    rec: ResearchSessionRecord,
    *,
    user_message: str,
    force_agents: list[str] | None = None,
    run_auditor: bool = False,
) -> MultiAgentTurnResponse:
    session_id = rec.session_id
    if rec.outcome is None:
        raise RuntimeError("session outcome missing")

    await session_store.store.append_transcript(
        session_id, _transcript_entry(role="user", content=user_message)
    )

    retrieved, source = await session_retrieval_context(rec, session_id, user_message)
    tail = _tail_transcript(rec.transcript)

    pipeline, rationale = await plan_agent_pipeline(
        topic=rec.topic,
        user_message=user_message,
        transcript=rec.transcript,
        force_agents=force_agents,
    )

    ctx = AgentContext(
        session_id=session_id,
        topic=rec.topic,
        user_message=user_message,
        outcome=rec.outcome,
        hydra_connected=rec.hydra_connected,
        transcript_tail=tail,
        retrieved_context=retrieved,
        context_source=source,
    )

    steps: list[AgentStepResult] = []
    for aid in pipeline:
        handler = HANDLERS.get(aid)
        if handler is None:
            continue
        result = await handler(ctx)
        steps.append(result)
        await session_store.store.append_transcript(
            session_id,
            _transcript_entry(role="assistant", content=result.content, agent=result.agent_id),
        )

    if not steps:
        fallback = await HANDLERS["interlocutor"](ctx)
        steps.append(fallback)
        await session_store.store.append_transcript(
            session_id,
            _transcript_entry(
                role="assistant", content=fallback.content, agent=fallback.agent_id
            ),
        )

    last_answer = steps[-1].content
    if run_auditor and last_answer:
        audit = await auditor_agent(ctx, last_answer)
        steps.append(audit)
        await session_store.store.append_transcript(
            session_id,
            _transcript_entry(role="assistant", content=audit.content, agent=audit.agent_id),
        )
        last_answer = f"{steps[-2].content}\n\n---\n**Auditor:** {audit.content}"

    invocations = [
        AgentInvocation(
            agent_id=s.agent_id,
            content=s.content,
            context_source=s.context_source,
        )
        for s in steps
    ]

    return MultiAgentTurnResponse(
        agents_invoked=invocations,
        router_rationale=rationale,
        final_answer=last_answer.strip(),
    )
