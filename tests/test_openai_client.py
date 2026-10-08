from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openai import APITimeoutError

from app.network.openai_client import (
    AiServiceError,
    complete,
    embed_texts,
    get_openai_client,
)


def _embedding_response(vectors):
    return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])


def _chat_response(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


# A plain AsyncMock is used rather than AsyncMock(spec=AsyncOpenAI): the SDK
# exposes calls through nested resource attributes (client.embeddings.create),
# which spec'ing does not reproduce usefully.


async def test_embed_texts_returns_vectors_in_order():
    client = AsyncMock()
    client.embeddings.create.return_value = _embedding_response([[0.1, 0.2], [0.3, 0.4]])

    result = await embed_texts(client, ["a", "b"], "text-embedding-3-small")

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    client.embeddings.create.assert_awaited_once_with(
        model="text-embedding-3-small", input=["a", "b"]
    )


async def test_embed_texts_short_circuits_on_empty_input():
    # OpenAI rejects an empty input array, so this must never reach the API.
    client = AsyncMock()

    result = await embed_texts(client, [], "text-embedding-3-small")

    assert result == []
    client.embeddings.create.assert_not_awaited()


async def test_embed_texts_raises_when_the_api_returns_fewer_vectors():
    # Silent zip() truncation would leave articles with a NULL embedding and an
    # endless backfill loop, so a count mismatch must be loud.
    client = AsyncMock()
    client.embeddings.create.return_value = _embedding_response([[0.1, 0.2]])

    with pytest.raises(AiServiceError):
        await embed_texts(client, ["a", "b"], "text-embedding-3-small")


async def test_embed_texts_wraps_api_errors():
    client = AsyncMock()
    client.embeddings.create.side_effect = APITimeoutError(request=None)

    with pytest.raises(AiServiceError):
        await embed_texts(client, ["a"], "text-embedding-3-small")


async def test_complete_returns_the_message_text():
    client = AsyncMock()
    client.chat.completions.create.return_value = _chat_response("A summary.")

    result = await complete(client, [{"role": "user", "content": "hi"}], "gpt-4o-mini")

    assert result == "A summary."


async def test_complete_wraps_api_errors():
    client = AsyncMock()
    client.chat.completions.create.side_effect = APITimeoutError(request=None)

    with pytest.raises(AiServiceError):
        await complete(client, [{"role": "user", "content": "hi"}], "gpt-4o-mini")


async def test_complete_raises_on_an_empty_response():
    client = AsyncMock()
    client.chat.completions.create.return_value = _chat_response(None)

    with pytest.raises(AiServiceError):
        await complete(client, [{"role": "user", "content": "hi"}], "gpt-4o-mini")


def test_get_openai_client_returns_none_without_a_key(monkeypatch):
    monkeypatch.setattr(
        "app.network.openai_client.get_settings",
        lambda: SimpleNamespace(openai_api_key=None),
    )
    assert get_openai_client() is None
