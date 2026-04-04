from __future__ import annotations

from typing import Any


def _triplet_line(triplet: dict[str, Any], *, indent: str = "") -> str:
    src = (triplet.get("source") or {}).get("name", "")
    tgt = (triplet.get("target") or {}).get("name", "")
    rel = triplet.get("relation") or {}
    pred = rel.get("canonical_predicate", "")
    line = f"{indent}[{src}] -> {pred} -> [{tgt}]"
    if rel.get("context"):
        line += f": {rel['context']}"
    if rel.get("temporal_details"):
        line += f" [Time: {rel['temporal_details']}]"
    return line


def _format_path_chain(path: Any) -> str:
    if not isinstance(path, dict):
        return str(path)
    triplets = path.get("triplets") or []
    return "\n  ↳ ".join(_triplet_line(t) for t in triplets)


def build_context_string(result: dict[str, Any]) -> str:
    lines: list[str] = []
    gc: dict[str, Any] = (result.get("graph_context") or {}) if isinstance(result, dict) else {}

    paths = gc.get("query_paths") or []
    if paths:
        lines.append("=== ENTITY PATHS ===")
        lines.extend(_format_path_chain(p) for p in paths)
        lines.append("")

    chunks: list[dict[str, Any]] = result.get("chunks") or []
    additional_context: dict[str, Any] = result.get("additional_context") or {}
    chunk_id_to_group_ids: dict[str, list[str]] = gc.get("chunk_id_to_group_ids") or {}
    chunk_relations: list[dict[str, Any]] = gc.get("chunk_relations") or []

    if not chunks:
        return "\n".join(lines)

    lines.append("=== CONTEXT ===")
    for i, chunk in enumerate(chunks):
        lines.append(f"Chunk {i + 1}")
        src = chunk.get("source_title") or chunk.get("source") or ""
        if src:
            lines.append(f"Source: {src}")
        lines.append(chunk.get("chunk_content") or chunk.get("content") or "")

        cid = chunk.get("chunk_uuid") or chunk.get("id") or ""
        if cid and chunk_id_to_group_ids and chunk_relations:
            gids = chunk_id_to_group_ids.get(cid, [])
            rels = [r for r in chunk_relations if r.get("group_id") in gids]
            if rels:
                lines.append("Graph Relations:")
                for rel in rels:
                    for t in rel.get("triplets") or []:
                        lines.append(_triplet_line(t, indent="  "))

        xids = chunk.get("extra_context_ids") or []
        if xids and additional_context:
            extras = [additional_context[x] for x in xids if x in additional_context]
            if extras:
                lines.append("Extra Context:")
                for ex in extras:
                    t = ex.get("source_title", "")
                    c = ex.get("chunk_content") or ex.get("content", "")
                    lines.append(f"  Related Context ({t}): {c}")

        lines.extend(["---", ""])

    return "\n".join(lines)
