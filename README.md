# Research Intern

**Research Intern** is a workflow for serious literature review: the user submits a **research topic**, the system pulls **recent arXiv papers**, stores them in **HydraDB** for recall and graph context, then drives a **thinking-style analysis** to surface **conflicts**, **gaps**, **hypotheses**, and **actionable ideas**.

## What the user gets

1. **Topic in** — Natural-language query (used as the arXiv `all:` search and as the Hydra recall query).
2. **Literature collected** — Recent papers (default up to 30) from the [arXiv Atom API](https://info.arxiv.org/help/api/user-manual.html), newest first.
3. **Memory + knowledge** — HydraDB **recall_preferences** (past sessions, preferences, traces) and **full_recall** (ingested sources + optional **graph** context) prime the analysis.
4. **Ingestion** — Each abstract is uploaded as markdown **knowledge** so later turns retrieve overlapping work automatically.
5. **Conflict & gap pass** — A structured **analysis prompt** asks your LLM to compare abstracts explicitly: contradictions, robust agreement, gaps, **testable hypotheses**, and **next-step ideas** (not a black-box summary).
6. **Thinking engine (optional)** — You can mirror an explicit chain-of-thought by calling `save_thinking_step` (hypothesis / verification flags) as the model steps through the prompt, then `save_session_synthesis` for the final brief.

Code does **not** call an LLM for you: it collects evidence, hydrates HydraDB, and hands you a **prompt** (or you wire your own model and persist outputs).

## Setup and tests

Install dependencies from the repo root (includes optional SQLite for persistent sessions):

```bash
pip install -r requirements.txt
```

Run tests (in-memory sessions do not require `aiosqlite`; the SQLite store test is skipped if it is missing):

```bash
pytest
```
