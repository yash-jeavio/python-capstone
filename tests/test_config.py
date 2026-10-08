from app.common.config import Settings, get_settings


def test_settings_load_database_urls():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    assert settings.test_database_url.startswith("postgresql")
    assert settings.database_url != settings.test_database_url


def test_ai_settings_have_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg2://u:p@localhost/test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    # Absence of a key is the 501 path, not a startup crash.
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.embedding_model == "text-embedding-3-small"


def test_openai_api_key_is_read_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@localhost/db")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg2://u:p@localhost/test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")

    settings = Settings(_env_file=None)

    assert settings.openai_api_key == "sk-test-123"
