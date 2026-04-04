from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import os
import uuid

from .config import load_dotenv
from .workflow import run_literature_phase


async def _async_main(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Research Intern: gather corpus + optional Hydra, then run OpenAI-compatible analysis "
            "(stdout is the model answer by default; use --prompt-only for the raw prompt)."
        ),
    )
    parser.add_argument(
        "topic",
        nargs="?",
        default="",
        help="Research topic (phrase search + Hydra query unless --raw-query)",
    )
    parser.add_argument(
        "-t",
        "--topic",
        dest="topic_flag",
        default="",
        metavar="TEXT",
        help="Same as positional topic (if both given, this wins)",
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Session id for ingestion metadata (default: random cli_… id)",
    )
    parser.add_argument("--max-papers", type=int, default=30, metavar="N")
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Do not upload abstracts to Hydra (recall still runs if Hydra is used)",
    )
    parser.add_argument(
        "--no-hydra",
        action="store_true",
        help="No Hydra: fetch arXiv and build prompt only (no API keys)",
    )
    parser.add_argument(
        "--restrict-session",
        action="store_true",
        help="Recall only chunks tagged with this session_id",
    )
    parser.add_argument(
        "--raw-query",
        action="store_true",
        help="Pass topic through as a raw arXiv search_query",
    )
    parser.add_argument(
        "--all-arxiv",
        action="store_true",
        help="Do not restrict arXiv to cs.CL / cs.AI / cs.LG / stat.ML",
    )
    parser.add_argument(
        "--arxiv-only",
        action="store_true",
        help="Only arXiv (disable all other corpus sources)",
    )
    parser.add_argument(
        "--wikipedia-max",
        type=int,
        default=2,
        metavar="N",
        help="Wikipedia summary pages (0=off). Default: 2",
    )
    parser.add_argument(
        "--crossref-max",
        type=int,
        default=4,
        metavar="N",
        help="Crossref works (0=off). Default: 4",
    )
    parser.add_argument(
        "--europepmc-max",
        type=int,
        default=0,
        metavar="N",
        help="Europe PMC hits (0=off). Default: 0",
    )
    parser.add_argument(
        "--pubmed-max",
        type=int,
        default=0,
        metavar="N",
        help="PubMed / NCBI E-utilities (0=off). Default: 0",
    )
    parser.add_argument(
        "--openalex-max",
        type=int,
        default=0,
        metavar="N",
        help="OpenAlex works search (0=off). Default: 0",
    )
    parser.add_argument(
        "--semantic-scholar-max",
        type=int,
        default=0,
        metavar="N",
        help="Semantic Scholar paper search (0=off; ~1s delay per call). Default: 0",
    )
    parser.add_argument(
        "--ingest-pause",
        type=float,
        default=0.6,
        metavar="SEC",
        help="Delay between Hydra uploads (default: 0.6)",
    )
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="Skip LLM: print/write only the analysis prompt (no API key needed)",
    )
    parser.add_argument(
        "--llm-stream",
        action="store_true",
        help="Stream LLM output to stderr as it arrives (e.g. NVIDIA reasoning + answer)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="",
        metavar="FILE",
        help="Write primary stdout content to this file (model analysis, or prompt with --prompt-only)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Less logging; primary output still on stdout or -o",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="DEBUG logging",
    )

    args = parser.parse_args(argv)
    topic = (args.topic_flag or args.topic or "").strip()
    if not topic:
        parser.error("topic required (positional or -t/--topic)")

    load_dotenv()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    session_id = args.session_id.strip() or f"cli_{uuid.uuid4().hex[:16]}"

    wiki_max = 0 if args.arxiv_only else max(0, args.wikipedia_max)
    xref_max = 0 if args.arxiv_only else max(0, args.crossref_max)
    epm_max = 0 if args.arxiv_only else max(0, args.europepmc_max)
    pm_max = 0 if args.arxiv_only else max(0, args.pubmed_max)
    oa_max = 0 if args.arxiv_only else max(0, args.openalex_max)
    s2_max = 0 if args.arxiv_only else max(0, args.semantic_scholar_max)

    llm_complete = not args.prompt_only
    has_llm_key = bool(
        (os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("NVIDIA_API_KEY", "").strip())
    )
    if llm_complete and not has_llm_key:
        print(
            "OPENAI_API_KEY or NVIDIA_API_KEY is not set. Add to .env, or use --prompt-only for the raw prompt.",
            file=sys.stderr,
        )
        return 2

    bridge = None
    if not args.no_hydra:
        try:
            from .hydra_research_bridge import HydraResearchBridge

            bridge = HydraResearchBridge()
        except ModuleNotFoundError as e:
            if e.name == "hydra_db" or (e.msg and "hydra" in e.msg.lower()):
                print(
                    "Hydra client is not installed (pip install hydra-db-python) "
                    "or a dependency is missing.",
                    file=sys.stderr,
                )
                print("Hint: use --no-hydra for arXiv-only.", file=sys.stderr)
                return 1
            raise
        except ValueError as e:
            print(f"Hydra: {e}", file=sys.stderr)
            print("Hint: use --no-hydra for arXiv-only (no API keys).", file=sys.stderr)
            return 1

    outcome = await run_literature_phase(
        bridge,
        topic=topic,
        session_id=session_id,
        max_papers=args.max_papers,
        ingest_to_knowledge=not args.no_ingest,
        restrict_arxiv_cs_stat_ml=not args.all_arxiv,
        raw_arxiv_query=args.raw_query,
        restrict_recall_to_session=args.restrict_session,
        ingest_pause_seconds=args.ingest_pause,
        wikipedia_max=wiki_max,
        crossref_max=xref_max,
        europepmc_max=epm_max,
        pubmed_max=pm_max,
        openalex_max=oa_max,
        semantic_scholar_max=s2_max,
        llm_complete=llm_complete,
        llm_stream=True if args.llm_stream else None,
    )

    text = outcome.final_analysis if outcome.final_analysis is not None else outcome.analysis_prompt
    if args.output:
        path = args.output
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        if not args.quiet:
            kind = "analysis" if outcome.final_analysis is not None else "prompt"
            print(
                f"Wrote {kind} ({len(text)} chars) to {path!r}; "
                f"{len(outcome.papers)} corpus items; arXiv: {outcome.arxiv_search_query!r}; "
                f"corpus_stats: {json.dumps(outcome.corpus_stats, sort_keys=True)}",
                file=sys.stderr,
            )
    else:
        print(text)
        if not args.quiet:
            print(
                f"\n---\n{len(outcome.papers)} corpus items | session: {session_id}\n"
                f"arXiv: {outcome.arxiv_search_query!r}\n"
                f"extras: {outcome.extra_source_summary or '(none)'}\n"
                f"corpus_stats: {json.dumps(outcome.corpus_stats, sort_keys=True)}",
                file=sys.stderr,
            )

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_async_main(None)))


if __name__ == "__main__":
    main()
