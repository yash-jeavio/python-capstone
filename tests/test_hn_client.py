# tests/test_hn_client.py
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.network.hn_client import fetch_all, fetch_comments, fetch_item, fetch_story_ids

BASE_URL = "https://hacker-news.firebaseio.com/v0"


def _mock_response(json_data):
    # A real client.get() response always has `.request` set by httpx; a bare
    # httpx.Response(...) built by hand does not, and httpx's raise_for_status()
    # requires it to be set (even for a 200), so attach one to match reality.
    response = httpx.Response(
        200, json=json_data, request=httpx.Request("GET", "https://example.com")
    )
    return response


@pytest.mark.asyncio
async def test_fetch_story_ids_calls_correct_url():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _mock_response([1, 2, 3])

    result = await fetch_story_ids(mock_client, "topstories")

    mock_client.get.assert_called_once_with(f"{BASE_URL}/topstories.json")
    assert result == [1, 2, 3]


@pytest.mark.asyncio
async def test_fetch_item_returns_data_on_success():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _mock_response({"id": 1, "title": "Test"})

    result = await fetch_item(mock_client, 1)

    assert result == {"id": 1, "title": "Test"}


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_failure():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.TimeoutException("timed out")

    result = await fetch_item(mock_client, 1)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_remote_protocol_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.RemoteProtocolError("Server disconnected")

    result = await fetch_item(mock_client, 1)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_http_status_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    request = httpx.Request("GET", f"{BASE_URL}/item/1.json")
    mock_client.get.side_effect = httpx.HTTPStatusError(
        "503 Service Unavailable", request=request, response=httpx.Response(503, request=request)
    )

    result = await fetch_item(mock_client, 1)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_malformed_json_body():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = httpx.Response(
        200, content=b"<html>not json</html>", request=httpx.Request("GET", "https://example.com")
    )

    result = await fetch_item(mock_client, 1)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_all_counts_failures_without_aborting_batch():
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    async def fake_get(url, *args, **kwargs):
        if url.endswith("topstories.json"):
            return _mock_response([1, 2])
        if url.endswith("beststories.json"):
            return _mock_response([2])
        if url.endswith("askstories.json"):
            return _mock_response([])
        if url.endswith("showstories.json"):
            return _mock_response([])
        if url.endswith("/1.json"):
            return _mock_response({"id": 1, "title": "One", "type": "story", "time": 1700000000})
        if url.endswith("/2.json"):
            raise httpx.TimeoutException("timed out")
        raise AssertionError(f"unexpected url {url}")

    mock_client.get.side_effect = fake_get

    # `async with httpx.AsyncClient(...) as client:` needs the patched class,
    # when called, to return something whose __aenter__ resolves to mock_client.
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__.return_value = mock_client
    mock_client_context.__aexit__.return_value = None

    with patch("app.network.hn_client.httpx.AsyncClient", return_value=mock_client_context):
        items_with_source, failed_count = await fetch_all(limit_per_list=2)

    assert failed_count == 2  # item 2 fails once for "top" and once for "best"
    assert len(items_with_source) == 1
    assert items_with_source[0][0]["id"] == 1


async def test_fetch_comments_returns_top_level_comment_text():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        _mock_response({"id": 1, "kids": [10, 11]}),
        _mock_response({"id": 10, "text": "First comment"}),
        _mock_response({"id": 11, "text": "Second comment"}),
    ]

    result = await fetch_comments(mock_client, 1)

    assert result == ["First comment", "Second comment"]


async def test_fetch_comments_respects_the_limit():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        _mock_response({"id": 1, "kids": list(range(100, 130))}),
        *[_mock_response({"id": i, "text": f"c{i}"}) for i in range(100, 110)],
    ]

    result = await fetch_comments(mock_client, 1, limit=10)

    assert len(result) == 10


async def test_fetch_comments_skips_deleted_dead_and_textless():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [
        _mock_response({"id": 1, "kids": [10, 11, 12, 13]}),
        _mock_response({"id": 10, "text": "Good"}),
        _mock_response({"id": 11, "deleted": True}),
        _mock_response({"id": 12, "dead": True, "text": "Spam"}),
        _mock_response({"id": 13, "id": 13}),
    ]

    result = await fetch_comments(mock_client, 1)

    assert result == ["Good"]


async def test_fetch_comments_returns_empty_when_story_has_no_kids():
    # Ask HN posts with no replies, and any story nobody has commented on.
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = _mock_response({"id": 1, "title": "Lonely"})

    assert await fetch_comments(mock_client, 1) == []


async def test_fetch_comments_returns_empty_when_the_story_fetch_fails():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ReadTimeout("too slow")

    assert await fetch_comments(mock_client, 1) == []
