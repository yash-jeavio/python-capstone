# tests/test_content_fetcher.py
from unittest.mock import AsyncMock

import httpx

from app.network.content_fetcher import fetch_article_text

ARTICLE_HTML = """
<html><body>
<nav>Home About Contact</nav>
<article><p>Rust achieves memory safety without a garbage collector.
It does this through an ownership system checked at compile time.</p></article>
<footer>Copyright 2026</footer>
</body></html>
"""


def _response(status=200, text="", content_type="text/html", url="https://example.com"):
    return httpx.Response(
        status,
        text=text,
        headers={"content-type": content_type},
        request=httpx.Request("GET", url),
    )


async def test_extracts_readable_text_and_drops_chrome():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text=ARTICLE_HTML)

    result = await fetch_article_text(client, "https://example.com/rust")

    assert "memory safety" in result
    assert "Home About Contact" not in result


async def test_follows_redirects():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text=ARTICLE_HTML)

    await fetch_article_text(client, "https://example.com/rust")

    assert client.get.await_args.kwargs["follow_redirects"] is True


async def test_returns_none_on_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(status=404, text="Not found")

    assert await fetch_article_text(client, "https://example.com/gone") is None


async def test_returns_none_on_timeout():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.side_effect = httpx.ReadTimeout("too slow")

    assert await fetch_article_text(client, "https://example.com/slow") is None


async def test_returns_none_for_non_html_content():
    # HN links to PDFs and images regularly; trafilatura cannot read them.
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text="%PDF-1.7", content_type="application/pdf")

    assert await fetch_article_text(client, "https://example.com/paper.pdf") is None


async def test_returns_none_when_nothing_extractable():
    # A JS-only shell or a paywall yields markup with no article body.
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = _response(text="<html><body><div id='root'></div></body></html>")

    assert await fetch_article_text(client, "https://example.com/spa") is None
