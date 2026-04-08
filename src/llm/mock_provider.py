import json
import time
from typing import AsyncIterator

import httpx

from src.llm.provider import BaseLLMProvider, LLMResponse


class MockProvider(BaseLLMProvider):
    """Provider that talks to the mock LLM server (OpenAI-compatible)."""

    def __init__(self, name: str, base_url: str, models: list[str] | None = None):
        super().__init__(
            name=name,
            models=models or ["mock-model"],
            base_url=base_url.rstrip("/"),
        )
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def chat_completion(
        self,
        messages: list[dict],
        model: str,
        stream: bool = False,
        **kwargs,
    ) -> LLMResponse | AsyncIterator[str]:
        payload = {"model": model, "messages": messages, "stream": stream}
        start = time.monotonic()

        if stream:
            return self._stream(payload, start)

        resp = await self._client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        latency = (time.monotonic() - start) * 1000

        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model),
            provider=self.name,
            usage=data.get("usage", {}),
            latency_ms=latency,
        )

    async def _stream(self, payload: dict, start: float) -> AsyncIterator[str]:
        async with self._client.stream(
            "POST", "/v1/chat/completions", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str == "[DONE]":
                    break
                chunk = json.loads(data_str)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
