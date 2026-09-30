from datetime import datetime, timezone

from sqlalchemy import any_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database.models import Article


def upsert_articles(session: Session, articles: list[dict]) -> tuple[int, int]:
    if not articles:
        return 0, 0

    existing_ids = {
        row.id
        for row in session.query(Article.id).filter(
            Article.id.in_([a["id"] for a in articles])
        )
    }

    now = datetime.now(timezone.utc)
    rows = [{**article, "fetched_at": now} for article in articles]

    stmt = pg_insert(Article).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "title": stmt.excluded.title,
            "url": stmt.excluded.url,
            "author": stmt.excluded.author,
            "score": stmt.excluded.score,
            "comment_count": stmt.excluded.comment_count,
            "sources": stmt.excluded.sources,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    session.execute(stmt)
    session.commit()

    created = sum(1 for a in articles if a["id"] not in existing_ids)
    updated = len(articles) - created
    return created, updated


def query_articles(
    session: Session,
    keyword: str | None,
    min_score: int | None,
    source: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> list[Article]:
    query = session.query(Article)

    if keyword:
        query = query.filter(Article.title.ilike(f"%{keyword}%"))
    if min_score is not None:
        query = query.filter(Article.score >= min_score)
    if source:
        query = query.filter(source == any_(Article.sources))

    if sort == "posted_at_desc":
        query = query.order_by(Article.posted_at.desc())
    else:
        query = query.order_by(Article.score.desc())

    offset = (page - 1) * page_size
    return query.offset(offset).limit(page_size).all()
