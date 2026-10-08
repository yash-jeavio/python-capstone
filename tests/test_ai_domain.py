from datetime import datetime, timezone

import pytest

from app.database.models import Article
from app.domains.ai import (
    MAX_CONTENT_CHARS,
    build_chat_messages,
    build_embedding_input,
    build_summary_messages,
    truncate_content,
)


def _article(id: int, title: str, summary: str | None = None, score: int = 10) -> Article:
    return Article(
        id=id, title=title, url=f"https://example.com/{id}", author="alice",
        score=score, comment_count=3, item_type="story", sources=["top"],
        posted_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        summary=summary,
    )


def test_embedding_input_is_title_alone_when_no_summary():
    assert build_embedding_input("Rust is fast", None) == "Rust is fast"


def test_embedding_input_combines_title_and_summary():
    result = build_embedding_input("Rust is fast", "A post about Rust performance.")
    assert "Rust is fast" in result
    assert "A post about Rust performance." in result


def test_embedding_input_treats_blank_summary_as_absent():
    # A model that returns whitespace must not pollute the vector with padding.
    assert build_embedding_input("Rust is fast", "   ") == "Rust is fast"


def test_truncate_leaves_short_content_untouched():
    assert truncate_content("short text") == "short text"


def test_truncate_caps_long_content():
    result = truncate_content("word " * 10_000)
    assert len(result) <= MAX_CONTENT_CHARS


def test_truncate_cuts_at_a_whitespace_boundary():
    # Splitting mid-word wastes a token and reads as corruption to the model.
    result = truncate_content("a" * 50 + " " + "b" * MAX_CONTENT_CHARS)
    assert not result.endswith("b")


def test_summary_messages_include_title_and_content():
    messages = build_summary_messages("Rust is fast", "Some article body.")

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Rust is fast" in messages[1]["content"]
    assert "Some article body." in messages[1]["content"]


def test_chat_messages_ground_the_answer_in_the_given_articles():
    articles = [_article(1, "Rust is fast", "About Rust."), _article(2, "Go is simple")]

    messages = build_chat_messages("Which language is faster?", articles)

    prompt = messages[1]["content"]
    assert "Which language is faster?" in prompt
    assert "Rust is fast" in prompt
    assert "Go is simple" in prompt
    # The system prompt must forbid answering outside the retrieved set.
    assert "only" in messages[0]["content"].lower()


def test_chat_messages_handle_an_empty_retrieval_set():
    messages = build_chat_messages("Anything?", [])
    assert "Anything?" in messages[1]["content"]
