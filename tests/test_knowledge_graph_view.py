"""Tests for :mod:`core.knowledge_graph_view`."""

from __future__ import annotations

from core.knowledge_graph_view import (
    build_knowledge_graph_view,
    format_knowledge_graph_for_prompt,
)


def test_build_knowledge_graph_view_empty():
    g = build_knowledge_graph_view(None, None)
    assert g["nodes"] == []
    assert g["edges"] == []
    assert g["paths"] == []
    assert g["stats"]["node_count"] == 0
    assert "meta" in g


def test_build_knowledge_graph_view_empty_graph_context_meta():
    """Hydra often returns graph_context keys with empty lists — meta should flag graph_lists_empty."""
    shell = {
        "graph_context": {
            "query_paths": [],
            "chunk_relations": [],
            "chunk_id_to_group_ids": {},
        }
    }
    g = build_knowledge_graph_view(shell, shell)
    assert g["stats"]["node_count"] == 0
    assert g["meta"]["full_recall"]["graph_context"] is True
    assert g["meta"]["full_recall"]["graph_lists_empty"] is True
    assert g["meta"]["full_recall"]["query_paths_len"] == 0
    assert g["meta"]["preferences"]["graph_lists_empty"] is True


def test_build_knowledge_graph_view_triplets_and_paths():
    full = {
        "graph_context": {
            "query_paths": [
                {
                    "triplets": [
                        {
                            "source": {"name": "Attention"},
                            "target": {"name": "Transformer"},
                            "relation": {
                                "canonical_predicate": "used_in",
                                "context": "NLP",
                            },
                        }
                    ]
                }
            ],
            "chunk_relations": [
                {
                    "group_id": "g1",
                    "triplets": [
                        {
                            "source": {"name": "BERT"},
                            "target": {"name": "Attention"},
                            "relation": {"canonical_predicate": "extends"},
                        }
                    ],
                }
            ],
        }
    }
    g = build_knowledge_graph_view(full, None)
    assert g["stats"]["triplet_count"] == 2
    assert g["stats"]["node_count"] == 3
    assert g["stats"]["edge_count"] == 2
    assert len(g["paths"]) == 1
    labels = {n["label"] for n in g["nodes"]}
    assert "Attention" in labels
    assert "Transformer" in labels
    assert "BERT" in labels


def test_query_paths_steps_and_chunk_relations_relations_key():
    """Hydra-style paths using ``steps`` and chunk groups using ``relations`` instead of ``triplets``."""
    full = {
        "graph_context": {
            "query_paths": [
                {
                    "steps": [
                        {
                            "source": {"name": "Alpha"},
                            "target": {"name": "Beta"},
                            "relation": "associated_with",
                        }
                    ]
                }
            ],
            "chunk_relations": [
                {
                    "group_id": "g1",
                    "relations": [
                        {
                            "source": {"name": "Gamma"},
                            "target": {"name": "Delta"},
                            "predicate": "cites",
                        }
                    ],
                }
            ],
        }
    }
    g = build_knowledge_graph_view(full, None)
    assert g["stats"]["triplet_count"] == 2
    assert g["stats"]["edge_count"] == 2
    preds = {e["predicate"] for e in g["edges"]}
    assert "associated_with" in preds
    assert "cites" in preds


def test_build_knowledge_graph_view_edges_and_subject_predicate():
    full = {
        "graph_context": {
            "edges": [
                {
                    "source": {"name": "X"},
                    "target": {"name": "Y"},
                    "predicate": "links_to",
                }
            ],
            "triplets": [
                {
                    "subject": {"name": "P"},
                    "object": {"name": "Q"},
                    "predicate": "mentions",
                }
            ],
        }
    }
    g = build_knowledge_graph_view(full, None)
    assert g["stats"]["triplet_count"] == 2
    preds = {e["predicate"] for e in g["edges"]}
    assert "links_to" in preds
    assert "mentions" in preds


def test_format_knowledge_graph_for_prompt():
    g = build_knowledge_graph_view(
        {
            "graph_context": {
                "query_paths": [
                    {
                        "triplets": [
                            {
                                "source": {"name": "A"},
                                "target": {"name": "B"},
                                "relation": {"canonical_predicate": "relates_to"},
                            }
                        ]
                    }
                ]
            }
        },
        None,
    )
    text = format_knowledge_graph_for_prompt(g)
    assert "Knowledge graph" in text
    assert "A" in text and "B" in text and "relates_to" in text


def test_format_knowledge_graph_for_prompt_empty():
    assert format_knowledge_graph_for_prompt(None) == ""
    assert format_knowledge_graph_for_prompt({}) == ""
