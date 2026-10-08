"""Pure AI helpers: prompt construction, truncation, embedding input.

No I/O and no database access -- everything here is a deterministic function of
its arguments, so it is tested without mocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.database.models import Article

# Bounds worst-case cost per summary and stays well inside gpt-4o-mini's context
# window. ~12k chars is roughly 3k tokens. Single source of truth for the limit.
MAX_CONTENT_CHARS = 12_000

SUMMARY_SYSTEM_PROMPT = (
    "You summarize technical articles and discussions from Hacker News. "
    "Write three to four sentences of plain prose. State what the content "
    "actually says; do not speculate beyond it and do not add a preamble."
)

CHAT_SYSTEM_PROMPT = (
    "You answer questions about a collection of Hacker News articles. "
    "Use only the articles provided in the user message. If they do not "
    "contain the answer, say so plainly rather than guessing. Refer to "
    "articles by their titles."
)


def build_embedding_input(title: str, summary: str | None) -> str:
    """Text to embed for an article: title alone, or title plus summary."""
    if summary and summary.strip():
        return f"{title}\n\n{summary.strip()}"
    return title


def truncate_content(text: str) -> str:
    """Cap content at MAX_CONTENT_CHARS, cutting at a whitespace boundary."""
    if len(text) <= MAX_CONTENT_CHARS:
        return text
    cut = text[:MAX_CONTENT_CHARS]
    boundary = cut.rfind(" ")
    # A single unbroken token longer than the limit has no boundary to cut at,
    # so fall back to the hard slice rather than returning an empty string.
    return cut[:boundary] if boundary > 0 else cut


def build_summary_messages(title: str, content: str) -> list[dict]:
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": f"Title: {title}\n\nContent:\n{content}"},
    ]


def build_chat_messages(question: str, articles: list[Article]) -> list[dict]:
    if articles:
        blocks = []
        for article in articles:
            lines = [f"Title: {article.title}", f"Score: {article.score}"]
            if article.url:
                lines.append(f"URL: {article.url}")
            if article.summary:
                lines.append(f"Summary: {article.summary}")
            blocks.append("\n".join(lines))
        context = "\n\n---\n\n".join(blocks)
    else:
        context = "(no articles matched this question)"

    return [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Articles:\n\n{context}\n\nQuestion: {question}"},
    ]
