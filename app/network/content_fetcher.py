# app/network/content_fetcher.py
import logging

import httpx
import trafilatura

logger = logging.getLogger("hn_capstone")


async def fetch_article_text(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a URL and extract its readable body text.

    Returns None for every failure mode -- unreachable host, non-2xx, non-HTML
    body, or markup with no extractable article. None is the caller's signal to
    fall back to the HN comment thread, so this never raises.
    """
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.info("Content fetch failed for %s: %s", url, exc)
        return None

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        logger.info("Skipping non-HTML content at %s (%s)", url, content_type)
        return None

    extracted = trafilatura.extract(response.text)
    if not extracted or not extracted.strip():
        logger.info("No extractable article body at %s", url)
        return None
    return extracted.strip()
