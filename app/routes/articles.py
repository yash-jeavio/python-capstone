from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.models import Article
from app.database.repository import query_articles, upsert_articles
from app.database.session import get_db
from app.domains.article import merge_batch
from app.network.hn_client import fetch_all

router = APIRouter()


@router.get("/articles")
def list_articles(
    keyword: str | None = None,
    min_score: int | None = Query(default=None, ge=0),
    source: str | None = None,
    sort: str = "score_desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    articles = query_articles(db, keyword, min_score, source, sort, page, page_size)
    return [
        {
            "id": a.id, "title": a.title, "url": a.url, "author": a.author,
            "score": a.score, "comment_count": a.comment_count,
            "item_type": a.item_type, "sources": a.sources,
            "posted_at": a.posted_at.isoformat(),
        }
        for a in articles
    ]


@router.get("/articles/{article_id}")
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return {
        "id": article.id, "title": article.title, "url": article.url,
        "author": article.author, "score": article.score,
        "comment_count": article.comment_count, "item_type": article.item_type,
        "sources": article.sources, "posted_at": article.posted_at.isoformat(),
    }


@router.post("/articles/refresh")
async def refresh_articles(db: Session = Depends(get_db)):
    items_with_source, failed = await fetch_all()
    merged = merge_batch(items_with_source)
    created, updated = upsert_articles(db, merged)
    return {"fetched": len(merged), "created": created, "updated": updated, "failed": failed}
