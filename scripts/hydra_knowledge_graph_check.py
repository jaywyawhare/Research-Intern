#!/usr/bin/env python3
"""
Inspect Hydra recall graph_context and the app's normalized knowledge graph.

Run from the repository root (with HYDRADB_* in .env):

  python scripts/hydra_knowledge_graph_check.py "your search query"
  python scripts/hydra_knowledge_graph_check.py "topic" --session-id sess_abc123
  python scripts/hydra_knowledge_graph_check.py --use-stored-topic --session-id sess_abc123
  python scripts/hydra_knowledge_graph_check.py --list-sessions
  python scripts/hydra_knowledge_graph_check.py --list-sessions --scan-mongo

Requires: pip install hydra-db-python (and project deps).
  --use-stored-topic reads the topic from MongoDB (MONGODB_URI).
  --list-sessions prints what is in MongoDB for the configured db/collection.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def resolve_stored_topic(session_id: str) -> tuple[str | None, list[str]]:
    """
    Load topic from MongoDB. Returns (topic_or_none, diagnostic_lines).
    """
    import os

    hints: list[str] = []
    if os.environ.get("SESSION_STORE", "").strip().lower() in ("memory", "ram") and not os.environ.get(
        "MONGODB_URI", ""
    ).strip():
        hints.append(
            "SESSION_STORE is memory/ram and MONGODB_URI is unset — the API did not persist sessions to MongoDB; "
            "--use-stored-topic cannot find this id. Copy the topic from the UI or your notes."
        )

    try:
        from backend.mongo_session_store import _motor_client_kwargs
    except Exception:  # pragma: no cover
        import certifi as _certifi

        def _motor_client_kwargs() -> dict[str, Any]:
            kw: dict[str, Any] = {"tlsCAFile": _certifi.where()}
            if os.environ.get("MONGODB_TLS_DISABLE_OCSP", "").strip().lower() in ("1", "true", "yes"):
                kw["tlsDisableOCSPEndpointCheck"] = True
            return kw

    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        hints.append("MONGODB_URI is not set — sessions are only stored in MongoDB. Set it in .env (same as the API).")
        return None, hints

    db = os.environ.get("MONGODB_DB", "ai_researcher").strip() or "ai_researcher"
    coll_name = os.environ.get("MONGODB_COLLECTION", "research_sessions").strip() or "research_sessions"

    try:
        from pymongo import MongoClient

        client = MongoClient(uri, **_motor_client_kwargs())
        try:
            col = client[db][coll_name]
            doc = col.find_one({"session_id": session_id}, {"topic": 1})
            if doc and doc.get("topic"):
                return str(doc["topic"]).strip(), hints
            hints.append(
                f"No document with session_id={session_id!r} in MongoDB {db!r}.{coll_name!r}."
            )
            sample = [
                x["session_id"]
                for x in col.find({}, {"session_id": 1}).sort("_id", -1).limit(5)
                if x.get("session_id")
            ]
            if sample:
                hints.append(f"Recent session_id values in that collection: {sample}")
        finally:
            client.close()
    except Exception as e:
        hints.append(f"MongoDB error ({type(e).__name__}): {e}")

    return None, hints


def _summarize_recall_payload(d: dict[str, Any]) -> dict[str, Any]:
    """Top-level recall shape (chunks vs empty graph)."""
    chunks = d.get("chunks")
    n_chunks = len(chunks) if isinstance(chunks, list) else 0
    sources = d.get("sources")
    n_sources = len(sources) if isinstance(sources, list) else 0
    ac = d.get("additional_context")
    n_ac = len(ac) if isinstance(ac, dict) else 0
    return {
        "top_level_keys": sorted(d.keys()),
        "chunks_count": n_chunks,
        "sources_count": n_sources,
        "additional_context_entries": n_ac,
    }


def _summarize_graph_context(gc: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(gc, dict):
        return {"present": False}
    out: dict[str, Any] = {"present": True, "keys": sorted(gc.keys())}
    for key in ("query_paths", "chunk_relations", "paths"):
        block = gc.get(key)
        if isinstance(block, list):
            out[f"{key}_len"] = len(block)
        elif isinstance(block, dict):
            out[f"{key}_keys"] = sorted(block.keys())[:40]
    return out


def _truncate(obj: Any, max_chars: int) -> str:
    s = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n... [truncated] ..."


async def _run(args: argparse.Namespace) -> int:
    from core import config as hydra_config
    from core.hydra_research_bridge import HydraResearchBridge
    from core.knowledge_graph_view import build_knowledge_graph_view

    hydra_config.load_dotenv()

    try:
        bridge = HydraResearchBridge()
    except ValueError as e:
        print(f"Config error: {e}", file=sys.stderr)
        print("Set HYDRADB_API_KEY and HYDRADB_TENANT_ID in .env (see .env.example).", file=sys.stderr)
        return 2

    meta: dict[str, Any] | None = None
    if args.session_id.strip():
        meta = {"session_id": args.session_id.strip()}

    ctx = await bridge.gather_context_for_topic(args.topic, metadata_filters=meta)
    full_d = ctx.get("full_recall_raw")
    pref_d = ctx.get("recall_preferences_raw")

    full_d = full_d if isinstance(full_d, dict) else {}
    pref_d = pref_d if isinstance(pref_d, dict) else {}

    gc_full = full_d.get("graph_context")
    gc_pref = pref_d.get("graph_context")

    print("=== Recall payload (besides graph) ===\n")
    print("full_recall:", json.dumps(_summarize_recall_payload(full_d), indent=2))
    print("recall_preferences:", json.dumps(_summarize_recall_payload(pref_d), indent=2))
    print()

    print("=== Hydra recall (graph_context) ===\n")
    print("full_recall.graph_context:", json.dumps(_summarize_graph_context(gc_full if isinstance(gc_full, dict) else None), indent=2))
    print()
    print("recall_preferences.graph_context:", json.dumps(_summarize_graph_context(gc_pref if isinstance(gc_pref, dict) else None), indent=2))
    print()

    kg = build_knowledge_graph_view(full_d, pref_d)
    print("=== Normalized knowledge_graph (this app) ===\n")
    print(json.dumps(kg.get("stats"), indent=2))
    print()
    print("meta:", json.dumps(kg.get("meta"), indent=2, default=str))
    print()

    stats = kg.get("stats") or {}
    triplets = int(stats.get("triplet_count") or 0)
    sf = _summarize_recall_payload(full_d)
    sp = _summarize_recall_payload(pref_d)
    fc, pc = sf["chunks_count"], sp["chunks_count"]
    print("=== Interpretation ===\n")
    if triplets == 0:
        if fc == 0 and pc == 0:
            print(
                "No text chunks in either recall response — Hydra had nothing to attach a graph to.\n"
                "  • Use the **same topic string** as the research session (the UI shows it), not a generic word like \"research\".\n"
                "  • With `--session-id`, recall only sees knowledge tagged for that session; if nothing matched, chunks stay 0.\n"
                "  • Sanity check: run once **without** `--session-id` and the same topic to see if chunks appear at all.\n"
                "  • Confirm ingest for that session finished in Hydra (abstracts uploaded with metadata.session_id)."
            )
        else:
            print(
                "Chunks were returned, but graph_context has no query_paths or chunk_relations "
                "(entity graph not populated for this response). The UI graph stays empty until Hydra "
                "fills those arrays — e.g. graph extraction enabled for your tenant and enough linked corpus."
            )
    else:
        print("Triplet data was extracted; the in-app knowledge graph should show nodes/edges for this payload.")
    print()

    if args.dump_json:
        out_path = Path(args.dump_json)
        payload = {
            "full_recall_raw": full_d,
            "recall_preferences_raw": pref_d,
            "knowledge_graph": kg,
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"Wrote full payload to {out_path.resolve()}")

    if args.print_graph_context:
        max_c = max(500, args.max_chars)
        if isinstance(gc_full, dict):
            print("--- full_recall.graph_context (JSON) ---\n")
            print(_truncate(gc_full, max_c))
            print()
        if isinstance(gc_pref, dict):
            print("--- recall_preferences.graph_context (JSON) ---\n")
            print(_truncate(gc_pref, max_c))
            print()

    return 0


def cmd_list_mongo_sessions(*, scan_all: bool) -> int:
    """Print what is stored in MongoDB (same env as the API)."""
    import os
    from urllib.parse import urlparse

    from pymongo import MongoClient

    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        print("MONGODB_URI is not set. Add it to .env (see .env.example).", file=sys.stderr)
        return 2

    try:
        from backend.mongo_session_store import _motor_client_kwargs
    except Exception:
        import certifi as _certifi

        def _motor_client_kwargs() -> dict[str, Any]:
            kw: dict[str, Any] = {"tlsCAFile": _certifi.where()}
            if os.environ.get("MONGODB_TLS_DISABLE_OCSP", "").strip().lower() in ("1", "true", "yes"):
                kw["tlsDisableOCSPEndpointCheck"] = True
            return kw

    try:
        host = urlparse(uri).hostname or "?"
    except Exception:
        host = "?"

    db_name = os.environ.get("MONGODB_DB", "ai_researcher").strip() or "ai_researcher"
    coll_name = os.environ.get("MONGODB_COLLECTION", "research_sessions").strip() or "research_sessions"

    client = MongoClient(uri, **_motor_client_kwargs())
    try:
        print(f"=== MongoDB host: {host} ===\n")
        print(f"Configured collection: {db_name!r}.{coll_name!r}\n")

        col = client[db_name][coll_name]
        n = col.count_documents({})
        print(f"Document count in configured collection: {n}\n")

        if n:
            print("session_id | status | topic (truncated)")
            print("-" * 72)
            for doc in col.find().sort("_id", -1).limit(30):
                sid = doc.get("session_id", "")
                topic = str(doc.get("topic") or "")[:72]
                st = str(doc.get("status") or "")
                print(f"{sid!s}\t{st!s}\t{topic!s}")
        else:
            print("(Collection is empty.)\n")

        if scan_all or n == 0:
            print("=== Non-empty collections (excluding system DBs) ===\n")
            for dbn in sorted(client.list_database_names()):
                if dbn in ("admin", "local", "config"):
                    continue
                db = client[dbn]
                for cn in sorted(db.list_collection_names()):
                    if cn.startswith("system."):
                        continue
                    c = db[cn]
                    try:
                        est = c.estimated_document_count()
                    except Exception:
                        est = -1
                    if est == 0:
                        continue
                    sample = c.find_one({}, {"session_id": 1})
                    has_sid = isinstance(sample, dict) and "session_id" in sample
                    print(f"  {dbn}.{cn}\t~{est} docs\tsession_id field: {has_sid}")
            print()
    finally:
        client.close()

    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Inspect Hydra graph_context and normalized knowledge graph.")
    p.add_argument(
        "topic",
        nargs="?",
        default="",
        help="Recall query (same as research topic). Omit if --use-stored-topic.",
    )
    p.add_argument(
        "--session-id",
        default="",
        help="Optional metadata_filters.session_id (scoped recall)",
    )
    p.add_argument(
        "--use-stored-topic",
        action="store_true",
        help="Load topic from MongoDB (MONGODB_URI in .env) for this --session-id",
    )
    p.add_argument(
        "--print-graph-context",
        action="store_true",
        help="Print raw graph_context JSON (truncated; use --max-chars)",
    )
    p.add_argument(
        "--max-chars",
        type=int,
        default=12000,
        help="Max characters when printing graph_context (default: 12000)",
    )
    p.add_argument(
        "--dump-json",
        metavar="FILE",
        default="",
        help="Write full recall payloads + knowledge_graph to this file",
    )
    p.add_argument(
        "--list-sessions",
        action="store_true",
        help="List sessions stored in MongoDB (MONGODB_URI / MONGODB_DB / MONGODB_COLLECTION) and exit",
    )
    p.add_argument(
        "--scan-mongo",
        action="store_true",
        help="With --list-sessions, also list non-empty collections across databases (find wrong db/collection)",
    )
    args = p.parse_args()

    from core import config as hydra_config

    hydra_config.load_dotenv()

    if args.list_sessions:
        raise SystemExit(cmd_list_mongo_sessions(scan_all=args.scan_mongo))

    if args.use_stored_topic:
        if not args.session_id.strip():
            p.error("--use-stored-topic requires --session-id")
        t, hints = resolve_stored_topic(args.session_id.strip())
        if not t:
            print("Could not resolve topic from the app session store.\n", file=sys.stderr)
            for h in hints:
                print(f"  • {h}", file=sys.stderr)
            raise SystemExit(2)
        print(f"Using topic from app session store: {t!r}\n")
        args.topic = t
    elif not args.topic.strip():
        p.error("topic is required (or pass --use-stored-topic with --session-id)")

    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
