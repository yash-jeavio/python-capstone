from datetime import datetime, timezone

from app.domains.article import merge_batch, normalize_item


def test_normalize_item_maps_hn_fields():
    raw = {
        "id": 1,
        "title": "Y Combinator",
        "url": "http://ycombinator.com",
        "by": "pg",
        "score": 57,
        "descendants": 3,
        "type": "story",
        "time": 1160418111,
    }
    result = normalize_item(raw, source="top")

    assert result["id"] == 1
    assert result["title"] == "Y Combinator"
    assert result["url"] == "http://ycombinator.com"
    assert result["author"] == "pg"
    assert result["score"] == 57
    assert result["comment_count"] == 3
    assert result["item_type"] == "story"
    assert result["sources"] == ["top"]
    assert result["posted_at"] == datetime.fromtimestamp(1160418111, tz=timezone.utc)


def test_normalize_item_defaults_missing_optional_fields():
    # Ask HN posts have no url; a brand new item may have no score/descendants yet
    raw = {"id": 2, "title": "Ask HN: anything", "by": "bob", "type": "story", "time": 1700000000}
    result = normalize_item(raw, source="ask")

    assert result["url"] is None
    assert result["score"] == 0
    assert result["comment_count"] == 0


def test_merge_batch_combines_sources_for_duplicate_id_in_same_batch():
    raw_top = {"id": 5, "title": "Popular", "by": "x", "score": 10,
               "descendants": 1, "type": "story", "time": 1700000000}
    raw_best = {"id": 5, "title": "Popular", "by": "x", "score": 15,
                "descendants": 2, "type": "story", "time": 1700000000}

    merged = merge_batch([(raw_top, "top"), (raw_best, "best")])

    assert len(merged) == 1
    assert merged[0]["id"] == 5
    assert sorted(merged[0]["sources"]) == ["best", "top"]
    # last-seen values win for fields that change over time
    assert merged[0]["score"] == 15
    assert merged[0]["comment_count"] == 2


def test_merge_batch_keeps_distinct_ids_separate():
    raw_a = {"id": 1, "title": "A", "by": "x", "score": 1, "descendants": 0,
             "type": "story", "time": 1700000000}
    raw_b = {"id": 2, "title": "B", "by": "y", "score": 2, "descendants": 0,
             "type": "story", "time": 1700000000}

    merged = merge_batch([(raw_a, "top"), (raw_b, "top")])

    assert {item["id"] for item in merged} == {1, 2}
