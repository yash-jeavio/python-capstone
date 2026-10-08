import logging

from openai import AsyncOpenAI, OpenAIError

from app.common.config import get_settings

logger = logging.getLogger("hn_capstone")


class AiServiceError(Exception):
    """An OpenAI call failed. Mapped to HTTP 503 -- transient, retry may work."""


def get_openai_client() -> AsyncOpenAI | None:
    """FastAPI dependency. Returns None when no API key is configured, which
    routes translate to 501 (not configured) rather than a failure."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_texts(client: AsyncOpenAI, texts: list[str], model: str) -> list[list[float]]:
    # OpenAI rejects an empty input array; a no-op backfill must not call out.
    if not texts:
        return []
    try:
        response = await client.embeddings.create(model=model, input=texts)
    except OpenAIError as exc:
        logger.warning("Embedding call failed: %s", exc)
        raise AiServiceError("embedding request failed") from exc

    vectors = [item.embedding for item in response.data]
    if len(vectors) != len(texts):
        # Pairing by zip() would silently drop articles and leave them NULL.
        raise AiServiceError(
            f"expected {len(texts)} embeddings, received {len(vectors)}"
        )
    return vectors


async def complete(client: AsyncOpenAI, messages: list[dict], model: str) -> str:
    try:
        response = await client.chat.completions.create(model=model, messages=messages)
    except OpenAIError as exc:
        logger.warning("Completion call failed: %s", exc)
        raise AiServiceError("completion request failed") from exc

    content = response.choices[0].message.content
    if not content:
        raise AiServiceError("completion returned no content")
    return content
