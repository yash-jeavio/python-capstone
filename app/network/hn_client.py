import asyncio

import httpx

BASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_LISTS = ["topstories", "beststories", "askstories", "showstories"]


async def fetch_story_ids(client: httpx.AsyncClient, list_name: str) -> list[int]:
    response = await client.get(f"{BASE_URL}/{list_name}.json")
    response.raise_for_status()
    return response.json()


async def fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None:
    try:
        response = await client.get(f"{BASE_URL}/item/{item_id}.json")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        # httpx.HTTPError covers timeouts, connect/read/write errors, protocol
        # errors and 4xx/5xx; ValueError covers a malformed JSON body. Best-effort:
        # one bad item must never abort the whole refresh.
        return None


async def fetch_all(limit_per_list: int = 30) -> tuple[list[tuple[dict, str]], int]:
    items_with_source: list[tuple[dict, str]] = []
    failed_count = 0

    async with httpx.AsyncClient(timeout=10) as client:
        for list_name in HN_LISTS:
            source = list_name.replace("stories", "")  # "topstories" -> "top"
            ids = (await fetch_story_ids(client, list_name))[:limit_per_list]

            results = await asyncio.gather(*(fetch_item(client, item_id) for item_id in ids))

            for raw_item in results:
                if raw_item is None:
                    failed_count += 1
                else:
                    items_with_source.append((raw_item, source))

    return items_with_source, failed_count


async def fetch_comments(
    client: httpx.AsyncClient, item_id: int, limit: int = 10
) -> list[str]:
    """Top-level comment bodies for a story, in HN's own `kids` ordering.

    Used as the summarization fallback when a story has no URL (Ask HN, text
    posts) or its linked page cannot be fetched. Best-effort like fetch_item:
    an unreachable story or comment yields fewer results, never an exception.
    """
    story = await fetch_item(client, item_id)
    if story is None:
        return []

    kid_ids = (story.get("kids") or [])[:limit]
    if not kid_ids:
        return []

    comments = await asyncio.gather(*(fetch_item(client, kid) for kid in kid_ids))
    return [
        comment["text"]
        for comment in comments
        if comment
        and not comment.get("deleted")
        and not comment.get("dead")
        and comment.get("text")
    ]
