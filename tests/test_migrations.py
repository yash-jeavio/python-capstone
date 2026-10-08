from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_head_revision():
    # Multiple heads mean someone branched migrations without merging; alembic
    # upgrade head then fails at runtime rather than at review time.
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert len(script.get_heads()) == 1


def test_baseline_creates_articles_table():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revisions = list(script.walk_revisions())
    source = open(revisions[-1].path).read()
    assert "articles" in source
    assert "create_table" in source
