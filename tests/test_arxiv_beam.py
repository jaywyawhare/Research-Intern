from core.arxiv_beam import _title_to_topic_phrase
from core.arxiv_literature import build_arxiv_search_query


def test_title_to_topic_phrase_skips_stopwords():
    t = "A Neural Model for Joint Learning of Bridge and Span"
    p = _title_to_topic_phrase(t, max_words=5)
    assert p is not None
    assert "Neural" in p
    assert p.lower().startswith("neural")


def test_title_to_topic_phrase_short_returns_none():
    assert _title_to_topic_phrase("AI") is None


def test_build_query_phrase_compatible_with_beam():
    q = build_arxiv_search_query("neural bridge span", restrict_cs_stat_ml=True, raw_arxiv_query=False)
    assert "all:" in q
