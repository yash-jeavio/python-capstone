from app.database.models import Article


def serialize_article(article: Article) -> dict:
    """The one definition of the article JSON shape returned by the API.

    Matches the `Article` interface in frontend/src/types/article.ts. Internal
    columns (fetched_at, summary, embedding) are deliberately excluded.
    """
    return {
        "id": article.id,
        "title": article.title,
        "url": article.url,
        "author": article.author,
        "score": article.score,
        "comment_count": article.comment_count,
        "item_type": article.item_type,
        "sources": article.sources,
        "posted_at": article.posted_at.isoformat(),
    }
