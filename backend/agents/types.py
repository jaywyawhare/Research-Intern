from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentContext:
    session_id: str
    topic: str
    user_message: str
    outcome: dict[str, Any]
    hydra_connected: bool
    transcript_tail: str
    retrieved_context: str
    context_source: str


@dataclass(frozen=True)
class AgentStepResult:
    agent_id: str
    content: str
    context_source: str | None = None
    retrieved_context: str | None = None
