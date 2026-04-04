from __future__ import annotations

import json
import logging
import os
import re
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)

_DISABLE_LOG = os.environ.get("DISABLE_THOUGHT_LOGGING", "").lower() in ("1", "true", "yes")

_CAMEL_TO_SNAKE: dict[str, str] = {
    "nextThoughtNeeded": "next_thought_needed",
    "thoughtNumber": "thought_number",
    "totalThoughts": "total_thoughts",
    "isRevision": "is_revision",
    "revisesThought": "revises_thought",
    "branchFromThought": "branch_from_thought",
    "branchId": "branch_id",
    "needsMoreThoughts": "needs_more_thoughts",
    "isHypothesis": "is_hypothesis",
    "isVerification": "is_verification",
    "returnFullHistory": "return_full_history",
    "autoIterate": "auto_iterate",
    "maxDepth": "max_depth",
}


class ThinkingValidationError(ValueError):
    """Invalid thought payload."""


def normalize_thought_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Accept camelCase (tool JSON) or snake_case keys."""
    out: dict[str, Any] = dict(raw)
    for camel, snake in _CAMEL_TO_SNAKE.items():
        if camel in out and snake not in out:
            out[snake] = out.pop(camel)
    return out


class ThinkingEngine:
    """Keeps thought history, optional branch buckets, validates each step."""

    def __init__(self) -> None:
        self.thought_history: list[dict[str, Any]] = []
        self.branches: dict[str, list[dict[str, Any]]] = {}

    def clear(self) -> None:
        self.thought_history.clear()
        self.branches.clear()

    def validate_input(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ThinkingValidationError("payload must be a dict")
        d = normalize_thought_payload(data)
        required = ("thought", "next_thought_needed", "thought_number", "total_thoughts")
        for key in required:
            if key not in d:
                raise ThinkingValidationError(f"missing required field: {key}")
        if not isinstance(d["thought"], str):
            raise ThinkingValidationError("'thought' must be a string")
        if not isinstance(d["next_thought_needed"], bool):
            raise ThinkingValidationError("'next_thought_needed' must be a boolean")
        if not isinstance(d["thought_number"], int) or d["thought_number"] < 1:
            raise ThinkingValidationError("'thought_number' must be an integer >= 1")
        if not isinstance(d["total_thoughts"], int) or d["total_thoughts"] < 1:
            raise ThinkingValidationError("'total_thoughts' must be an integer >= 1")
        for opt, msg in (
            ("is_hypothesis", "'is_hypothesis' must be a boolean or omitted"),
            ("is_verification", "'is_verification' must be a boolean or omitted"),
            ("is_revision", "'is_revision' must be a boolean or omitted"),
        ):
            if opt in d and d[opt] is not None and not isinstance(d[opt], bool):
                raise ThinkingValidationError(msg)
        return d

    @staticmethod
    def format_thought(thought_data: dict[str, Any]) -> str:
        if thought_data.get("is_verification"):
            prefix = "Verification"
        elif thought_data.get("is_hypothesis"):
            prefix = "Hypothesis"
        elif thought_data.get("is_revision"):
            prefix = "Revision"
        elif thought_data.get("branch_from_thought"):
            prefix = "Branch"
        else:
            prefix = "Thought"
        ctx = ""
        if thought_data.get("is_revision") and thought_data.get("revises_thought") is not None:
            ctx = f" (revises step {thought_data['revises_thought']})"
        elif thought_data.get("branch_from_thought"):
            bid = thought_data.get("branch_id", "")
            ctx = f" (from step {thought_data['branch_from_thought']}, branch={bid})"
        header = f"{prefix} {thought_data['thought_number']}/{thought_data['total_thoughts']}{ctx}"
        body = thought_data["thought"]
        w = max(len(header), len(body), 20)
        line = "─" * (w + 2)
        return f"┌{line}┐\n│ {header.ljust(w)} │\n├{line}┤\n│ {body.ljust(w)} │\n└{line}┘"

    @staticmethod
    def extract_branches(thought_text: str) -> list[str]:
        found: set[str] = set()
        if re.search(
            r"\b(should|do you|is it right|is it wrong|must|could|would|can you)\b",
            thought_text,
            re.I,
        ):
            found.update(("yes", "no"))
        if re.search(
            r"\b(consequence|outcome|result|harm|benefit|cost|save|risk|reward|loss|gain)\b",
            thought_text,
            re.I,
        ):
            found.add("consequentialist")
        if re.search(
            r"\b(rule|law|duty|obligation|right|wrong|moral|immoral|principle)\b",
            thought_text,
            re.I,
        ):
            found.add("rule_based")
        if re.search(r"\b(risk|uncertain|unknown|chance|probability|possibility)\b", thought_text, re.I):
            found.add("risk_analysis")
        if not found:
            found.add("continue")
        return list(found)

    def auto_generate_thoughts(
        self,
        initial_data: dict[str, Any],
        *,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Breadth-first expansion using :meth:`extract_branches` (excluding ``continue``)."""
        out: list[dict[str, Any]] = []
        queue: list[tuple[dict[str, Any], int]] = [(deepcopy(initial_data), 0)]
        seen: set[str] = set()

        def sig(x: dict[str, Any]) -> str:
            return json.dumps(
                {
                    "t": x.get("thought"),
                    "n": x.get("thought_number"),
                    "b": x.get("branch_id"),
                    "f": x.get("branch_from_thought"),
                },
                sort_keys=True,
            )

        while queue:
            cur, depth = queue.pop(0)
            cur = {k: v for k, v in cur.items() if not callable(v)}
            sk = sig(cur)
            if sk in seen or depth >= max_depth:
                continue
            seen.add(sk)
            out.append(dict(cur))
            for b in self.extract_branches(cur["thought"]):
                if b == "continue":
                    continue
                nxt = deepcopy(cur)
                nxt["thought"] = f"[{b}] {cur['thought']}"
                nxt["branch_id"] = b
                nxt["branch_from_thought"] = cur["thought_number"]
                nxt["thought_number"] = int(cur["thought_number"]) + 1
                queue.append((nxt, depth + 1))
        return out

    def process_thought(self, data: dict[str, Any]) -> dict[str, Any]:
        td = self.validate_input(data)
        row = {k: v for k, v in td.items() if not hasattr(v, "__dict__") and not callable(v)}
        if row["thought_number"] > row["total_thoughts"]:
            row["total_thoughts"] = row["thought_number"]
        self.thought_history.append(dict(row))
        bid = row.get("branch_id")
        bfrom = row.get("branch_from_thought")
        if bid and bfrom is not None:
            self.branches.setdefault(str(bid), []).append(dict(row))
        if not _DISABLE_LOG:
            logger.info("%s", self.format_thought(row))

        response: dict[str, Any] = {
            "thought_number": row["thought_number"],
            "total_thoughts": row["total_thoughts"],
            "next_thought_needed": row["next_thought_needed"],
            "branches": list(self.branches.keys()),
            "thought_history_length": len(self.thought_history),
        }
        if row.get("is_hypothesis"):
            response["hypothesis"] = row["thought"]
        if row.get("is_verification"):
            response["verification"] = row["thought"]
        if row.get("return_full_history"):
            response["thought_history"] = [dict(t) for t in self.thought_history]
        if row.get("auto_iterate"):
            depth = int(row.get("max_depth") or 5)
            response["auto_generated"] = self.auto_generate_thoughts(row, max_depth=depth)
        return response


async def persist_thought_to_hydra(
    bridge: Any,
    *,
    session_id: str,
    engine: ThinkingEngine,
    payload: dict[str, Any],
    title: str | None = None,
) -> dict[str, Any]:
    """Run :meth:`ThinkingEngine.process_thought` and store the step in Hydra memory."""
    from .hydra_research_bridge import HydraResearchBridge

    if not isinstance(bridge, HydraResearchBridge):
        raise TypeError("bridge must be HydraResearchBridge")
    result = engine.process_thought(payload)
    last = engine.thought_history[-1]
    step = int(last["thought_number"])
    ttl = title if title else f"Thinking step {step}"
    await bridge.save_thinking_step(
        session_id=session_id,
        step_index=step,
        title=ttl[:500],
        text=last["thought"],
    )
    return result
