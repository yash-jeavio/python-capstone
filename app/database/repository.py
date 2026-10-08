from datetime import datetime, timezone

from sqlalchemy import any_, text, update
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
            # Historical union: every HN list this article has ever appeared in,
            # across all refreshes -- not just the lists from this refresh.
            # Raw SQL on purpose: SQLAlchemy won't correlate a subquery inside
            # ON CONFLICT ... SET and instead emits `FROM articles, articles AS
            # excluded`, a cross join over the whole table.
            "sources": text(
                "array(select distinct unnest(articles.sources || excluded.sources))"
            ),
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
        query = query.order_by(Article.posted_at.desc(), Article.id.desc())
    else:
        query = query.order_by(Article.score.desc(), Article.id.desc())

    offset = (page - 1) * page_size
    return query.offset(offset).limit(page_size).all()


def articles_missing_embeddings(session: Session) -> list[Article]:
    """Articles with no vector yet -- the backfill target."""
    return session.query(Article).filter(Article.embedding.is_(None)).all()


def store_embeddings(
    session: Session, pairs: list[tuple[Article, list[float]]]
) -> None:
    """Attach vectors to articles in one transaction.

    The backfill reads its `pending` list (embedding IS NULL) before this
    writes, so another session's write -- e.g. /summary's store_summary,
    which writes a vector derived from title+summary -- can land in between.
    The WHERE clause makes this a no-op for any row that is no longer NULL,
    enforced by Postgres itself rather than a Python `is None` check that
    cannot see another session's already-committed write.
    """
    for article, embedding in pairs:
        result = session.execute(
            update(Article)
            .where(Article.id == article.id, Article.embedding.is_(None))
            .values(embedding=embedding)
        )
        if result.rowcount:
            article.embedding = embedding
    session.commit()


def store_summary(
    session: Session, article: Article, summary: str, embedding: list[float]
) -> None:
    """Write a summary and its refreshed vector together.

    One transaction on purpose: the vector is derived from title + summary, so a
    committed summary paired with a stale vector would be an inconsistent state
    that nothing later repairs (the backfill only looks for NULL embeddings).
    """
    article.summary = summary
    article.summary_generated_at = datetime.now(timezone.utc)
    article.embedding = embedding
    session.commit()


def find_similar(
    session: Session,
    embedding: list[float],
    limit: int = 5,
    exclude_id: int | None = None,
) -> list[Article]:
    """Nearest articles by cosine distance, computed in Postgres by pgvector."""
    query = session.query(Article).filter(Article.embedding.is_not(None))
    if exclude_id is not None:
        query = query.filter(Article.id != exclude_id)
    return (
        query.order_by(Article.embedding.cosine_distance(embedding)).limit(limit).all()
    )
