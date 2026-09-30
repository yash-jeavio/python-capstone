from datetime import datetime, timezone


def normalize_item(raw_item: dict, source: str) -> dict:
    return {
        "id": raw_item["id"],
        "title": raw_item["title"],
        "url": raw_item.get("url"),
        "author": raw_item.get("by"),
        "score": raw_item.get("score", 0),
        "comment_count": raw_item.get("descendants", 0),
        "item_type": raw_item["type"],
        "sources": [source],
        "posted_at": datetime.fromtimestamp(raw_item["time"], tz=timezone.utc),
    }


def is_skippable(raw_item: dict) -> bool:
    # Deleted/dead HN items (e.g. {"id": 123, "deleted": true}) and items with no
    # title/time are not real articles -- unlike url/score/descendants there is no
    # sensible default for these, so they are skipped rather than normalized.
    return bool(
        raw_item.get("deleted")
        or raw_item.get("dead")
        or "title" not in raw_item
        or "time" not in raw_item
    )


def merge_batch(items: list[tuple[dict, str]]) -> tuple[list[dict], int]:
    """Normalize and merge a batch. Returns (merged_articles, skipped_count)."""
    merged: dict[int, dict] = {}
    skipped = 0

    for raw_item, source in items:
        if is_skippable(raw_item):
            skipped += 1
            continue

        normalized = normalize_item(raw_item, source)
        item_id = normalized["id"]

        if item_id not in merged:
            merged[item_id] = normalized
        else:
            existing = merged[item_id]
            existing["sources"] = sorted(set(existing["sources"]) | {source})
            existing["score"] = normalized["score"]
            existing["comment_count"] = normalized["comment_count"]

    return list(merged.values()), skipped
