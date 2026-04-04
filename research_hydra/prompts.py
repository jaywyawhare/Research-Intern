from __future__ import annotations

from .arxiv_literature import PaperRecord


def build_analysis_prompt(
    *,
    topic: str,
    user_context: str,
    knowledge_context: str,
    papers: tuple[PaperRecord, ...],
    arxiv_search_query: str = "",
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
    lines += [
        "### Prior memory (from HydraDB recall_preferences)\n",
        user_context.strip() or "(none retrieved)",
        "",
        "### Prior knowledge base (from HydraDB full_recall)\n",
        knowledge_context.strip() or "(none retrieved)",
        "",
        "### Corpus for this run (recent arXiv abstracts)\n",
    ]
    for i, p in enumerate(papers, start=1):
        lines += [
            f"#### Paper {i}: {p.title}\n",
            f"- **arXiv:** `{p.arxiv_id}`  **Published:** {p.published}\n",
            f"- **URL:** {p.abs_url}\n",
            f"\n{p.summary}\n\n---\n",
        ]
    lines += [
        "",
        "## Your tasks",
        "",
        "1. **Conflicts** — Contradictions across papers; cite by title or arXiv id.",
        "2. **Agreement & robustness** — Where results converge; strength of evidence.",
        "3. **Research gaps** — Under-studied or weakly supported areas.",
        "4. **Hypotheses** — Testable hypotheses for top gaps.",
        "5. **Ideas** — Next steps: experiments, data, reading, methods.",
        "",
        "Label speculation vs abstract-backed claims clearly.",
    ]
    return "\n".join(lines)
