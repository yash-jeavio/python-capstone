from app.common.config import get_settings


def test_settings_load_database_urls():
    settings = get_settings()
    assert settings.database_url.startswith("postgresql")
    assert settings.test_database_url.startswith("postgresql")
    assert settings.database_url != settings.test_database_url
