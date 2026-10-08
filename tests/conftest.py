import pytest
from sqlalchemy import text

from app.common.config import get_settings
from app.database.session import Base, engine_for, session_factory_for


@pytest.fixture
def db_session():
    engine = engine_for(get_settings().test_database_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    session_factory = session_factory_for(engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
