import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.telemetry.metrics import record_llm_request, record_llm_error, record_tokens

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "mock-model"
    messages: list[ChatMessage]
    stream: bool = False


@router.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    balancer = request.app.state.balancer

    messages = [m.model_dump() for m in body.messages]
    start = time.monotonic()

    try:
        if body.stream:
            result = await balancer.route_request(
                messages=messages, model=body.model, stream=True
            )
            return StreamingResponse(
                _wrap_sse(result),
                media_type="text/event-stream",
            )

        result = await balancer.route_request(
            messages=messages, model=body.model, stream=False
        )
        duration = time.monotonic() - start
        record_llm_request(result.provider, result.model, "ok", duration)
        record_tokens(
            result.provider,
            result.model,
            result.usage.get("prompt_tokens", 0),
            result.usage.get("completion_tokens", 0),
        )

        return {
            "id": "chatcmpl-proxy",
            "object": "chat.completion",
            "model": result.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.content},
                    "finish_reason": "stop",
                }
            ],
            "usage": result.usage,
            "provider": result.provider,
            "latency_ms": result.latency_ms,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        duration = time.monotonic() - start
        record_llm_error("unknown", type(e).__name__)
        raise HTTPException(status_code=502, detail=f"LLM request failed: {e}")


async def _wrap_sse(stream):
    """Wrap an async token iterator into SSE format."""
    async for token in stream:
        chunk = {
            "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


@router.get("/health")
async def health(request: Request):
    balancer = request.app.state.balancer
    statuses = await balancer.health_check_all()
    all_healthy = all(statuses.values())
    return {
        "status": "ok" if all_healthy else "degraded",
        "providers": statuses,
    }


@router.get("/providers")
async def list_providers(request: Request):
    balancer = request.app.state.balancer
    result = []
    for p in balancer.providers:
        healthy = await p.health_check()
        result.append({
            "name": p.name,
            "models": p.models,
            "healthy": healthy,
        })
    return {"providers": result}
