import time
from typing import AsyncIterator

from anthropic import AsyncAnthropic

from src.llm.provider import BaseLLMProvider, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    """Provider wrapping the Anthropic SDK."""

    def __init__(self, api_key: str, models: list[str] | None = None):
        super().__init__(
            name="anthropic",
            models=models or ["claude-3-haiku-20240307", "claude-sonnet-4-20250514"],
        )
        self._client = AsyncAnthropic(api_key=api_key)

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse | AsyncIterator[str]:
        # Anthropic requires separating system message
        system_text = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_text += m["content"] + "\n"
            else:
                chat_messages.append({"role": m["role"], "content": m["content"]})

        if not chat_messages:
            chat_messages = [{"role": "user", "content": "Hello"}]

        start = time.monotonic()

        if stream:
            return self._stream(chat_messages, model, system_text.strip(), start)

        params = dict(model=model, messages=chat_messages, max_tokens=1024)
        if system_text.strip():
            params["system"] = system_text.strip()

        resp = await self._client.messages.create(**params)
        latency = (time.monotonic() - start) * 1000

        content = resp.content[0].text if resp.content else ""

        return LLMResponse(
            content=content,
            model=resp.model,
            provider=self.name,
            usage={
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            },
            latency_ms=latency,
        )

    async def _stream(
        self,
        messages: list[dict],
        model: str,
        system: str,
        start: float,
    ) -> AsyncIterator[str]:
        params = dict(model=model, messages=messages, max_tokens=1024)
        if system:
            params["system"] = system

        async with self._client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            # Light request to verify credentials
            await self._client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.close()
