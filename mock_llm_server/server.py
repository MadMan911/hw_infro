"""Mock LLM server that mimics OpenAI Chat Completions API.

Supports configurable latency and error rate via environment variables:
  MOCK_LATENCY_MS  — base response latency in milliseconds (default: 100)
  MOCK_ERROR_RATE  — probability of returning a 500 error (0.0–1.0, default: 0.0)
"""

import asyncio
import json
import os
import random
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mock LLM Server")

LATENCY_MS = int(os.getenv("MOCK_LATENCY_MS", "100"))
ERROR_RATE = float(os.getenv("MOCK_ERROR_RATE", "0.0"))

MOCK_RESPONSES = [
    "Здравствуйте! Я помогу вам с вашим вопросом.",
    "Для решения этой проблемы попробуйте перезагрузить устройство.",
    "Ваш запрос зарегистрирован, специалист свяжется с вами в ближайшее время.",
    "Проверьте настройки в личном кабинете в разделе «Услуги».",
    "Баланс вашего счёта можно проверить в мобильном приложении или на сайте.",
]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Simulate errors
    if random.random() < ERROR_RATE:
        return {"error": {"message": "Internal server error", "type": "server_error"}}, 500

    body = await request.json()
    model = body.get("model", "mock-model")
    stream = body.get("stream", False)
    messages = body.get("messages", [])

    response_text = random.choice(MOCK_RESPONSES)
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # Simulate latency
    await asyncio.sleep(LATENCY_MS / 1000.0)

    if stream:
        return StreamingResponse(
            _stream_response(completion_id, model, response_text),
            media_type="text/event-stream",
        )

    # Non-streaming response
    prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)
    completion_tokens = len(response_text.split())

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def _stream_response(completion_id: str, model: str, text: str):
    """Yield SSE chunks token-by-token, mimicking OpenAI streaming format."""
    tokens = text.split(" ")
    for i, token in enumerate(tokens):
        chunk_text = token if i == 0 else f" {token}"
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk_text},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        await asyncio.sleep(0.02)  # 20ms between tokens

    # Final chunk with finish_reason
    final_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"
