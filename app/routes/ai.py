import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.common.config import Settings, get_settings
from app.database.models import Article
from app.database.repository import (
    articles_missing_embeddings,
    find_similar,
    store_embeddings,
    store_summary,
)
from app.database.session import get_db
from app.domains.ai import build_embedding_input, build_summary_messages, truncate_content
from app.network.content_fetcher import fetch_article_text
from app.network.hn_client import fetch_comments
from app.network.openai_client import complete, embed_texts, get_openai_client
from app.routes.serializers import serialize_article

logger = logging.getLogger("hn_capstone")

RETRIEVAL_LIMIT = 5
CONTENT_TIMEOUT_SECONDS = 10

router = APIRouter()


def require_client(client: AsyncOpenAI | None) -> AsyncOpenAI:
    """501, not 5xx: no key is an expected configuration state, not a fault."""
    if client is None:
        raise HTTPException(status_code=501, detail="AI features are not configured")
    return client


async def ensure_embeddings(
    db: Session, client: AsyncOpenAI, settings: Settings
) -> None:
    """Embed every article that has no vector yet, in one batched call.

    Idempotent and shared by both corpus endpoints. On a fresh database the
    first call embeds the whole corpus; afterwards it covers only what the most
    recent refresh added, and is a no-op when nothing is missing.
    """
    pending = articles_missing_embeddings(db)
    if not pending:
        return

    texts = [build_embedding_input(a.title, a.summary) for a in pending]
    vectors = await embed_texts(client, texts, settings.embedding_model)
    store_embeddings(db, list(zip(pending, vectors)))
    logger.info("Backfilled %d embeddings", len(pending))


@router.get("/articles/{article_id}/related")
async def get_related(
    article_id: int,
    db: Session = Depends(get_db),
    client: AsyncOpenAI | None = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    openai = require_client(client)
    await ensure_embeddings(db, openai, settings)

    related = find_similar(
        db, article.embedding, limit=RETRIEVAL_LIMIT, exclude_id=article.id
    )
    return {"related": [serialize_article(a) for a in related]}


async def _acquire_content(article: Article) -> str | None:
    """Page text when there is a fetchable URL, otherwise the HN discussion.

    Returns None only when both paths yield nothing, which the caller maps to 503.
    """
    async with httpx.AsyncClient(timeout=CONTENT_TIMEOUT_SECONDS) as http_client:
        if article.url:
            page_text = await fetch_article_text(http_client, article.url)
            if page_text:
                return page_text
        comments = await fetch_comments(http_client, article.id)

    joined = "\n\n".join(comments).strip()
    return joined or None


@router.get("/articles/{article_id}/summary")
async def get_summary(
    article_id: int,
    db: Session = Depends(get_db),
    client: AsyncOpenAI | None = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    # Cache check precedes the key check on purpose: an already-summarized
    # article keeps working even if the API key is later removed.
    if article.summary is not None:
        return {"summary": article.summary}

    openai = require_client(client)

    content = await _acquire_content(article)
    if content is None:
        logger.info("No content available to summarize article %d", article.id)
        raise HTTPException(
            status_code=503, detail="Could not retrieve content to summarize"
        )

    messages = build_summary_messages(article.title, truncate_content(content))
    summary = await complete(openai, messages, settings.openai_model)

    # Re-embed from title + summary so the vector matches the new summary.
    vectors = await embed_texts(
        openai,
        [build_embedding_input(article.title, summary)],
        settings.embedding_model,
    )
    store_summary(db, article, summary, vectors[0])

    return {"summary": summary}
