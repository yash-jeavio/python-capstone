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
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError):
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
