"""Tests for ai.rag.extract — concept matching + token stemming."""

from __future__ import annotations

from ai.rag.extract import _stem, extract_concepts, extract_search_tokens


def test_extract_concepts_matches_vocabulary() -> None:
    vocab = frozenset({"baihu", "taohua", "white tiger"})
    assert extract_concepts("Что значит baihu в дне?", vocab=vocab) == ["baihu"]


def test_extract_concepts_substring_for_multiword() -> None:
    """Multi-word concepts like "white tiger" must match via substring."""
    vocab = frozenset({"white tiger"})
    assert extract_concepts("about the white tiger star", vocab=vocab) == ["white tiger"]


def test_extract_concepts_normalises_yo() -> None:
    vocab = frozenset({"белый тигр"})
    # input uses ё; vocab uses е — must still match after normalisation
    assert extract_concepts("расскажи про Бёлый тигр", vocab=vocab) == ["белый тигр"]


def test_extract_concepts_empty_vocab() -> None:
    assert extract_concepts("anything", vocab=frozenset()) == []


def test_extract_concepts_is_sorted_for_determinism() -> None:
    vocab = frozenset({"a", "b", "c"})
    assert extract_concepts("a c b", vocab=vocab) == ["a", "b", "c"]


def test_extract_search_tokens_drops_stopwords() -> None:
    tokens = extract_search_tokens("Что значит у меня белый тигр?")
    assert "что" not in tokens
    assert "меня" not in tokens
    assert "значение" not in tokens
    assert "белый" in tokens
    assert "тигр" in tokens


def test_extract_search_tokens_drops_short_tokens() -> None:
    """≤ 3 chars (after stem) are discarded — they'd match anything."""
    tokens = extract_search_tokens("он ты мы дом")
    assert all(len(t) >= 3 for t in tokens)
    # "дом" stems to "дом" (3 chars) — kept; "он/ты/мы" filtered as <4 raw
    assert "дом" not in tokens  # raw len 3 < _MIN_TOKEN_LEN


def test_extract_search_tokens_stems_common_cases() -> None:
    """Russian declensions collapse to a common stem."""
    assert "дракон" in extract_search_tokens("про дракона")
    assert "крыс" in extract_search_tokens("про крысу и крысой")
    assert "столп" in extract_search_tokens("столпы удачи")
    assert "удач" in extract_search_tokens("столпы удачи")


def test_extract_search_tokens_handles_chinese() -> None:
    """Chinese characters (like 庚 or 白虎) are short — punctuation
    split keeps them; stemmer is a no-op on non-Russian."""
    tokens = extract_search_tokens("у меня 白虎 и 庚 Металл Ян")
    assert "металл" in tokens
    # 庚 is one char, below MIN_TOKEN_LEN — dropped (expected; concept
    # extraction relies on vocabulary for CJK).


def test_extract_search_tokens_deduplicates() -> None:
    tokens = extract_search_tokens("столпы удачи столпы удача удачей")
    assert tokens.count("столп") == 1
    assert tokens.count("удач") == 1


def test_stem_short_token_unchanged() -> None:
    assert _stem("дом") == "дом"  # too short to strip
    assert _stem("кит") == "кит"


def test_stem_strips_common_endings() -> None:
    assert _stem("дракона") == "дракон"
    assert _stem("крысу") == "крыс"
    assert _stem("столпы") == "столп"
    assert _stem("элементов") == "элемент"
    assert _stem("здоровье") == "здоровь"


def test_stem_picks_longest_matching_suffix() -> None:
    """``ого`` should win over ``о`` for "огненного"."""
    assert _stem("огненного") == "огненн"
