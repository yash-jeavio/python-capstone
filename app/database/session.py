from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.common.config import get_settings


class Base(DeclarativeBase):
    pass


def engine_for(database_url: str):
    return create_engine(database_url)


def session_factory_for(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Production engine/session, built from DATABASE_URL (not TEST_DATABASE_URL).
# Importing this module does not open a connection yet -- create_engine()
# is lazy, so this is safe even before the dev Postgres container is up.
engine = engine_for(get_settings().database_url)
SessionLocal = session_factory_for(engine)


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
