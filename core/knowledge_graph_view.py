from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

def _stable_id(prefix: str, s: str) -> str:
    h = hashlib.sha256(s.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{prefix}_{h}"


def _entity_pair(ent: Any) -> tuple[str, str]:
    if not isinstance(ent, dict):
        t = str(ent).strip() or "unknown"
        return _stable_id("e", t), t[:200]
    name = (ent.get("name") or ent.get("label") or "").strip()
    uid = ent.get("id") or ent.get("uuid") or ent.get("entity_id")
    if uid is not None and str(uid).strip():
        sid = str(uid).strip()
        return sid, name or sid
    if name:
        slug = re.sub(r"[^\w\-.]+", "_", name, flags=re.UNICODE)[:56].strip("_") or "entity"
        return _stable_id("n", name), name[:200]
    return _stable_id("e", repr(ent)), "(unnamed entity)"


def _as_entity(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {"name": "?"}
    if isinstance(obj, dict):
        return obj
    return {"name": str(obj)}


def _normalize_triplet_dict(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Map subject/object/head/tail style payloads into source/target/relation."""
    src = (
        raw.get("source")
        or raw.get("subject")
        or raw.get("head")
        or raw.get("s")
        or raw.get("from_entity")
        or raw.get("head_entity")
    )
    tgt = (
        raw.get("target")
        or raw.get("object")
        or raw.get("tail")
        or raw.get("o")
        or raw.get("to_entity")
        or raw.get("tail_entity")
    )
    if src is None and tgt is None:
        return None
    rel = raw.get("relation")
    if isinstance(rel, dict):
        rel_d = rel
    elif isinstance(rel, str):
        rel_d = {"canonical_predicate": rel}
    else:
        pred = raw.get("predicate") or raw.get("canonical_predicate") or raw.get("type") or raw.get("edge_type")
        if isinstance(pred, str):
            rel_d = {"canonical_predicate": pred}
        else:
            rel_d = {}
    return {
        "source": _as_entity(src) if src is not None else {"name": "?"},
        "target": _as_entity(tgt) if tgt is not None else {"name": "?"},
        "relation": rel_d,
    }


def _edge_dict_to_triplet(e: dict[str, Any]) -> dict[str, Any] | None:
    s = e.get("source") or e.get("from") or e.get("head") or e.get("subject")
    t = e.get("target") or e.get("to") or e.get("tail") or e.get("object")
    if s is None or t is None:
        return None
    pred = e.get("predicate") or e.get("relation") or e.get("label") or "related_to"
    if isinstance(pred, dict):
        rel: dict[str, Any] = pred
    else:
        rel = {"canonical_predicate": str(pred)}
    return {"source": _as_entity(s), "target": _as_entity(t), "relation": rel}


# Hydra / provider variants nest relations under these keys on a path or chunk group object.
_CONTAINER_TRIPLET_KEYS = (
    "triplets",
    "triplet",
    "steps",
    "chain",
    "path",
    "relations",
    "edges",
    "items",
    "link_chain",
    "path_triplets",
    "graph_relations",
)


def _append_triplets_from_container(obj: Mapping[str, Any], out: list[dict[str, Any]]) -> None:
    """Pull triplet-like dicts from common nested keys (steps, relations, …)."""
    for key in _CONTAINER_TRIPLET_KEYS:
        block = obj.get(key)
        if isinstance(block, list):
            for item in block:
                if not isinstance(item, dict):
                    continue
                n = _normalize_triplet_dict(item)
                if n:
                    out.append(n)
                    continue
                n2 = _edge_dict_to_triplet(item)
                if n2:
                    out.append(n2)
        elif isinstance(block, dict) and key == "triplet":
            n = _normalize_triplet_dict(block)
            if n:
                out.append(n)


def _triplets_from_graph_context(gc: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not gc:
        return []
    out: list[dict[str, Any]] = []
    for p in gc.get("query_paths") or []:
        if isinstance(p, dict):
            _append_triplets_from_container(p, out)

    cr_raw = gc.get("chunk_relations")
    cr_iter: list[Any]
    if isinstance(cr_raw, dict):
        cr_iter = list(cr_raw.values())
    elif isinstance(cr_raw, list):
        cr_iter = cr_raw
    else:
        cr_iter = []
    for cr in cr_iter:
        if isinstance(cr, dict):
            _append_triplets_from_container(cr, out)
        elif isinstance(cr, list):
            for item in cr:
                if isinstance(item, dict):
                    n = _normalize_triplet_dict(item) or _edge_dict_to_triplet(item)
                    if n:
                        out.append(n)

    for key in ("triplets", "triples", "relations"):
        block = gc.get(key)
        if not isinstance(block, list):
            continue
        for item in block:
            if isinstance(item, dict):
                n = _normalize_triplet_dict(item)
                if n:
                    out.append(n)
    for e in gc.get("edges") or []:
        if isinstance(e, dict):
            n = _edge_dict_to_triplet(e)
            if n:
                out.append(n)
    return out


def _triplets_from_recall_result(result: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not result:
        return []
    out: list[dict[str, Any]] = []
    gc = result.get("graph_context")
    if isinstance(gc, dict):
        out.extend(_triplets_from_graph_context(gc))
    for key in ("triplets", "triples", "relations"):
        block = result.get(key)
        if not isinstance(block, list):
            continue
        for item in block:
            if isinstance(item, dict):
                n = _normalize_triplet_dict(item)
                if n:
                    out.append(n)
    return out


def _relation_dict_from_triplet(t: dict[str, Any]) -> dict[str, Any]:
    """Normalize ``relation`` whether it is a dict, string, or top-level ``predicate``."""
    r = t.get("relation")
    if isinstance(r, dict):
        return r
    if isinstance(r, str):
        return {"canonical_predicate": r, "context": ""}
    p = t.get("predicate") or t.get("canonical_predicate") or t.get("type")
    if isinstance(p, str):
        out: dict[str, Any] = {"canonical_predicate": p}
        c = t.get("context")
        if isinstance(c, str) and c:
            out["context"] = c
        return out
    return {}


def _triplets_from_single_path_dict(p: Mapping[str, Any]) -> list[dict[str, Any]]:
    acc: list[dict[str, Any]] = []
    _append_triplets_from_container(p, acc)
    return acc


def _path_dicts_from_graph_context(gc: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(gc, dict):
        return []
    merged: list[dict[str, Any]] = []
    for key in ("query_paths", "paths"):
        for p in gc.get(key) or []:
            if isinstance(p, dict):
                merged.append(p)
    return merged


def _graph_lists_empty(gc: Mapping[str, Any]) -> bool:
    """True when Hydra sent the usual keys but no paths, relation groups, or chunk→group links."""
    qp = gc.get("query_paths")
    cr = gc.get("chunk_relations")
    cm = gc.get("chunk_id_to_group_ids")
    n_qp = len(qp) if isinstance(qp, list) else 0
    if isinstance(cr, list):
        n_cr = len(cr)
    elif isinstance(cr, dict):
        n_cr = len(cr)
    else:
        n_cr = 0
    n_cm = len(cm) if isinstance(cm, dict) else 0
    return n_qp == 0 and n_cr == 0 and n_cm == 0


def _recall_graph_meta(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"recall_present": False}
    gc = raw.get("graph_context")
    if not isinstance(gc, dict):
        return {"recall_present": True, "graph_context": False}
    return {
        "recall_present": True,
        "graph_context": True,
        "graph_context_keys": sorted(gc.keys()),
        "query_paths_len": len(gc["query_paths"]) if isinstance(gc.get("query_paths"), list) else 0,
        "chunk_relations_len": (
            len(gc["chunk_relations"])
            if isinstance(gc.get("chunk_relations"), (list, dict))
            else 0
        ),
        "chunk_id_to_group_ids_len": len(gc["chunk_id_to_group_ids"])
        if isinstance(gc.get("chunk_id_to_group_ids"), dict)
        else 0,
        "graph_lists_empty": _graph_lists_empty(gc),
    }


def build_knowledge_graph_view(
    full_recall_raw: Mapping[str, Any] | None,
    preferences_raw: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build ``nodes``, ``edges``, ``paths``, and ``meta`` from Hydra recall payloads.

    Accepts the shapes used by :mod:`context_builder` (``graph_context.query_paths`` /
    ``chunk_relations[].triplets``), plus common variants: flat ``triplets`` / ``edges`` lists,
    ``subject``/``object`` triples, and top-level ``triplets`` on the recall object.
    """
    triplets: list[dict[str, Any]] = []
    triplets.extend(_triplets_from_recall_result(full_recall_raw))
    triplets.extend(_triplets_from_recall_result(preferences_raw))

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def ensure_node(eid: str, label: str, *, kind: str = "entity") -> None:
        if eid not in nodes:
            nodes[eid] = {"id": eid, "label": label, "kind": kind}
        elif len(label) > len(nodes[eid].get("label") or ""):
            nodes[eid]["label"] = label

    for i, t in enumerate(triplets):
        src_ent = t.get("source")
        tgt_ent = t.get("target")
        rel = _relation_dict_from_triplet(t)
        sid, slabel = _entity_pair(src_ent)
        tid, tlabel = _entity_pair(tgt_ent)
        pred = (rel.get("canonical_predicate") or rel.get("predicate") or "related_to")[:200]
        ctx = (rel.get("context") or "")[:500]
        ensure_node(sid, slabel)
        ensure_node(tid, tlabel)
        eid = _stable_id("edge", f"{sid}|{pred}|{tid}|{i}")
        edges.append(
            {
                "id": eid,
                "source": sid,
                "target": tid,
                "source_label": slabel,
                "target_label": tlabel,
                "predicate": pred,
                "context": ctx or None,
            }
        )

    paths_out: list[dict[str, Any]] = []
    gc_full = (full_recall_raw or {}).get("graph_context") if isinstance(full_recall_raw, dict) else None
    gc_pref = (preferences_raw or {}).get("graph_context") if isinstance(preferences_raw, dict) else None
    path_idx = 0
    for gc in (x for x in (gc_full, gc_pref) if isinstance(x, dict)):
        for p in _path_dicts_from_graph_context(gc):
            if not isinstance(p, dict):
                continue
            triplets_in_path = _triplets_from_single_path_dict(p)
            if not triplets_in_path:
                continue
            parts: list[str] = []
            for tr in triplets_in_path:
                _, s_lab = _entity_pair(tr.get("source"))
                _, t_lab = _entity_pair(tr.get("target"))
                r = _relation_dict_from_triplet(tr)
                pr = r.get("canonical_predicate") or r.get("predicate") or "related_to"
                parts.append(f"[{s_lab}] - {pr} -> [{t_lab}]")
            paths_out.append(
                {
                    "id": _stable_id("path", str(path_idx) + repr(parts)),
                    "summary": "  ↳ ".join(parts),
                    "triplet_count": len(triplets_in_path),
                }
            )
            path_idx += 1

    meta = {
        "full_recall": _recall_graph_meta(full_recall_raw),
        "preferences": _recall_graph_meta(preferences_raw),
    }

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "paths": paths_out,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "triplet_count": len(triplets),
            "path_count": len(paths_out),
        },
        "meta": meta,
    }


def format_knowledge_graph_for_prompt(
    kg: Mapping[str, Any] | None,
    *,
    max_chars: int = 12_000,
    max_edges: int = 100,
    max_paths: int = 30,
) -> str:
    """
    Render a stored ``knowledge_graph`` dict (from :func:`build_knowledge_graph_view`) as markdown
    for LLM context. Returns empty string if there is nothing to say.
    """
    if not kg or not isinstance(kg, dict):
        return ""
    stats = kg.get("stats") if isinstance(kg.get("stats"), dict) else {}
    nodes = kg.get("nodes") if isinstance(kg.get("nodes"), list) else []
    edges = kg.get("edges") if isinstance(kg.get("edges"), list) else []
    paths = kg.get("paths") if isinstance(kg.get("paths"), list) else []
    n_n = int(stats.get("node_count", len(nodes)))
    n_e = int(stats.get("edge_count", len(edges)))
    n_p = int(stats.get("path_count", len(paths)))
    if n_n == 0 and n_e == 0 and n_p == 0:
        return ""

    lines: list[str] = ["## Knowledge graph (recall entities and relations)", ""]
    lines.append(
        f"Summary: {n_n} entities, {n_e} relations, {n_p} query path(s) from graph recall."
    )
    lines.append("")

    shown_e = 0
    for e in edges:
        if shown_e >= max_edges:
            break
        if not isinstance(e, dict):
            continue
        sl = str(e.get("source_label") or e.get("source") or "?")[:300]
        tl = str(e.get("target_label") or e.get("target") or "?")[:300]
        pr = str(e.get("predicate") or "related_to")[:200]
        ctx = e.get("context")
        line = f"- [{sl}] — *{pr}* → [{tl}]"
        if isinstance(ctx, str) and ctx.strip():
            line += f" ({ctx.strip()[:200]})"
        lines.append(line)
        shown_e += 1
    if len(edges) > shown_e:
        lines.append(f"- … ({len(edges) - shown_e} more relations omitted)")

    lines.append("")
    lines.append("### Entity labels (sample)")
    for n in nodes[: min(40, len(nodes))]:
        if not isinstance(n, dict):
            continue
        lab = str(n.get("label") or n.get("id") or "")[:200]
        if lab:
            lines.append(f"- {lab}")
    if len(nodes) > 40:
        lines.append(f"- … ({len(nodes) - 40} more)")

    shown_paths = 0
    if paths:
        lines.append("")
        lines.append("### Multi-hop paths")
        for p in paths:
            if shown_paths >= max_paths:
                break
            if not isinstance(p, dict):
                continue
            s = str(p.get("summary") or "").strip()
            if s:
                lines.append(f"- {s}")
                shown_paths += 1
        if len(paths) > shown_paths:
            lines.append(f"- … ({len(paths) - shown_paths} more paths omitted)")

    text = "\n".join(lines).strip()
    return text[:max_chars]
