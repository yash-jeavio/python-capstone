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


def merge_batch(items: list[tuple[dict, str]]) -> list[dict]:
    merged: dict[int, dict] = {}

    for raw_item, source in items:
        normalized = normalize_item(raw_item, source)
        item_id = normalized["id"]

        if item_id not in merged:
            merged[item_id] = normalized
        else:
            existing = merged[item_id]
            existing["sources"] = sorted(set(existing["sources"]) | {source})
            existing["score"] = normalized["score"]
            existing["comment_count"] = normalized["comment_count"]

    return list(merged.values())
