import time
from typing import AsyncIterator

from openai import AsyncOpenAI

from src.llm.provider import BaseLLMProvider, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    """Provider wrapping the OpenAI SDK."""

    def __init__(self, api_key: str, models: list[str] | None = None):
        super().__init__(
            name="openai",
            models=models or ["gpt-4o-mini", "gpt-4o"],
        )
        self._client = AsyncOpenAI(api_key=api_key)

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse | AsyncIterator[str]:
        start = time.monotonic()

        if stream:
            return self._stream(messages, model, start)

        resp = await self._client.chat.completions.create(
            model=model,
            messages=messages,
        )
        latency = (time.monotonic() - start) * 1000

        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=resp.model,
            provider=self.name,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                "total_tokens": resp.usage.total_tokens if resp.usage else 0,
            },
            latency_ms=latency,
        )

    async def _stream(
        self, messages: list[dict], model: str, start: float
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.close()
