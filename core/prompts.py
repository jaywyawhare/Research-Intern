from __future__ import annotations

from .arxiv_literature import PaperRecord


def build_analysis_prompt(
    *,
    topic: str,
    user_context: str,
    knowledge_context: str,
    papers: tuple[PaperRecord, ...],
    arxiv_search_query: str = "",
    extra_source_summary: str = "",
) -> str:
    lines: list[str] = [
        "You are Research Intern: a careful literature analyst.",
        "",
        f"## Research topic\n\n{topic.strip()}",
        "",
    ]
    if arxiv_search_query.strip():
        lines += [
            "### arXiv search query (exact API string)\n",
            f"\n`{arxiv_search_query.strip()}`\n",
            "",
        ]
    if extra_source_summary.strip():
        lines += [
            "### Keyless web sources (no API keys)\n",
            f"\n{extra_source_summary.strip()}\n",
            "",
        ]
    lines += [
        "### Prior memory (from HydraDB recall_preferences)\n",
        user_context.strip() or "(none retrieved)",
        "",
        "### Prior knowledge base (from HydraDB full_recall)\n",
        knowledge_context.strip() or "(none retrieved)",
        "",
        "### Corpus for this run (arXiv first, then keyless web excerpts)\n",
    ]
    for i, p in enumerate(papers, start=1):
        lines += [f"#### Item {i}: {p.title}\n"]
        lines += [
            f"- **Source:** {p.source}  **ID:** `{p.arxiv_id}`  **Published:** {p.published}\n",
            f"- **URL:** {p.abs_url}\n",
        ]
        if p.authors:
            au = ", ".join(p.authors[:10])
            if len(p.authors) > 10:
                au += ", …"
            lines.append(f"- **Authors:** {au}\n")
        if p.venue:
            lines.append(f"- **Venue:** {p.venue}\n")
        if p.citation_count:
            lines.append(f"- **Cited by (metadata):** {p.citation_count}\n")
        lines += [f"\n{p.summary}\n\n---\n"]
    lines += [
        "",
        "## Your tasks",
        "",
        "1. **Conflicts** — Contradictions across items; cite by title, URL, or id.",
        "2. **Agreement & robustness** — Where results converge; strength of evidence.",
        "3. **Research gaps** — Under-studied or weakly supported areas.",
        "4. **Hypotheses** — Testable hypotheses for top gaps.",
        "5. **Ideas** — Next steps: experiments, data, reading, methods.",
        "",
        "Label speculation vs abstract-backed claims clearly.",
    ]
    return "\n".join(lines)


def build_thinking_protocol_prompt(
    *,
    task: str,
    background: str = "",
    suggested_steps: int = 5,
    json_only: bool = True,
) -> str:
    """
    Instructions for an LLM to emit structured thought steps for ``ThinkingEngine.process_thought``.

    One JSON object per turn (snake_case keys; camelCase also accepted by the engine).
    """
    bg = background.strip()
    n = max(1, min(suggested_steps, 50))
    out: list[str] = [
        "You are a careful analyst using an explicit, revisable thinking protocol.",
        "",
        "## Task",
        "",
        task.strip(),
        "",
    ]
    if bg:
        out += ["## Background / evidence to use", "", bg, ""]
    out += [
        "## Protocol",
        "",
        "Work in discrete steps. Each step is one concise thought. You may revise earlier steps, "
        "branch alternatives, name a hypothesis, then verify it. Increase `total_thoughts` if you "
        "underestimated depth; keep `thought_number` monotonic for the main line (branches may use "
        "`branch_from_thought` / `branch_id`).",
        "",
        "### Required fields (every step)",
        "",
        "- `thought` (string): the content of this step.",
        "- `next_thought_needed` (boolean): true if you will continue after this message.",
        "- `thought_number` (integer ≥ 1): current step index (start at 1).",
        f"- `total_thoughts` (integer ≥ 1): running estimate of total steps; start around {n}, adjust up if needed.",
        "",
        "### Optional fields",
        "",
        "- `is_revision` / `revises_thought`: mark a correction to a prior step number.",
        "- `branch_from_thought` / `branch_id`: mark an exploratory branch from a prior step.",
        "- `is_hypothesis`: this step states a testable hypothesis.",
        "- `is_verification`: this step checks or refutes a hypothesis or claim.",
        "- `return_full_history`: if true, the runtime may echo full history (tool/backend dependent).",
        "- `auto_iterate` / `max_depth`: only if the runtime supports automatic branch expansion.",
        "",
        "### Output shape",
        "",
    ]
    if json_only:
        out += [
            "Reply with **a single JSON object** only (no markdown fence, no prose before or after).",
            "Use snake_case keys as listed above.",
            "",
            "Example:",
            "",
            '{"thought": "Frame the unknowns and success criteria.", "next_thought_needed": true, '
            '"thought_number": 1, "total_thoughts": 5}',
            "",
        ]
    else:
        out += [
            "Emit one step as JSON (object as above). You may add a short natural-language preface if needed.",
            "",
        ]
    out += [
        "## Quality bar",
        "",
        "Be specific; cite evidence from the background when present; separate facts from guesses; "
        "end with `next_thought_needed`: false only when the task is fully addressed.",
    ]
    return "\n".join(out)
