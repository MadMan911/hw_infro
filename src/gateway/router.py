import asyncio
import json
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.telemetry.metrics import record_llm_error, record_llm_request, record_tokens

router = APIRouter()


# ─── Helpers ───

def _require_scope(request: Request, scope: str) -> None:
    """Raise 403 if authenticated token lacks the required scope."""
    payload = getattr(request.state, "token_payload", None)
    if payload is None:
        return  # auth not enabled
    from src.auth.token_auth import token_auth
    if not token_auth.has_scope(payload, scope):
        raise HTTPException(status_code=403, detail=f"Missing scope: {scope}")


# ─── LLM proxy endpoint ───

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "mock-model"
    messages: list[ChatMessage]
    stream: bool = False


@router.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    _require_scope(request, "chat:read")
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


async def _wrap_sse(stream: AsyncIterator[str]):
    """Wrap an async token iterator into SSE format."""
    async for token in stream:
        chunk = {
            "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


# ─── Agent chat endpoint ───

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    stream: bool = False


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """Multi-agent chat endpoint. Routes through LangGraph. Supports SSE streaming."""
    _require_scope(request, "chat:read")

    graph = request.app.state.agent_graph
    if graph is None:
        raise HTTPException(status_code=503, detail="Agent graph not initialized")

    # Guardrails input check
    guardrails = getattr(request.app.state, "guardrails", None)
    message = body.message
    if guardrails:
        gr = await guardrails.check_input(message)
        if gr.blocked:
            raise HTTPException(status_code=400, detail=gr.reason)
        if gr.modified_text is not None:
            message = gr.modified_text

    try:
        from src.routing.graph import run_graph
        result = await run_graph(graph, message)

        final_response = result.get("final_response", "")

        # Guardrails output check
        if guardrails:
            gr_out = await guardrails.check_output(final_response)
            if gr_out.blocked:
                final_response = "Ответ был отфильтрован системой безопасности."
            elif gr_out.modified_text is not None:
                final_response = gr_out.modified_text

        if body.stream:
            async def _stream_response():
                routing_event = {
                    "type": "routing",
                    "visited_agents": result.get("visited_agents", []),
                }
                yield f"data: {json.dumps(routing_event)}\n\n"
                # Simulated streaming: the full response is already computed above.
                # True token-level streaming would require passing stream=True into
                # the LiteLLM ReAct loop and piping tokens via asyncio.Queue.
                for word in final_response.split(" "):
                    chunk = {"type": "token", "content": word + " "}
                    yield f"data: {json.dumps(chunk)}\n\n"
                    await asyncio.sleep(0.05)
                yield "data: [DONE]\n\n"

            return StreamingResponse(_stream_response(), media_type="text/event-stream")

        return {
            "response": final_response,
            "agent_trace": result.get("agent_trace", []),
            "visited_agents": result.get("visited_agents", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent processing failed: {e}")


# ─── Agent registry endpoints ───

class AgentCardRequest(BaseModel):
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    supported_methods: list[str] = []
    supported_topics: list[str] = []
    llm_requirements: dict = {}
    status: str = "active"


@router.get("/agents")
async def list_agents(request: Request):
    _require_scope(request, "agents:read")
    registry = request.app.state.agent_registry
    agents = await registry.list_all()
    return {"agents": [a.model_dump() for a in agents]}


@router.get("/agents/search")
async def search_agents(request: Request, method: str = "", topic: str = ""):
    _require_scope(request, "agents:read")
    registry = request.app.state.agent_registry
    if method:
        results = await registry.find_by_method(method)
    elif topic:
        results = await registry.find_by_topic(topic)
    else:
        results = await registry.list_all()
    return {"agents": [a.model_dump() for a in results]}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, request: Request):
    _require_scope(request, "agents:read")
    registry = request.app.state.agent_registry
    try:
        card = await registry.get(agent_id)
        return card.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")


@router.post("/agents/register")
async def register_agent(body: AgentCardRequest, request: Request):
    _require_scope(request, "agents:write")
    registry = request.app.state.agent_registry
    from datetime import datetime, timezone

    from src.agents.registry import AgentCard
    card = AgentCard(
        id=body.id,
        name=body.name,
        description=body.description,
        version=body.version,
        supported_methods=body.supported_methods,
        supported_topics=body.supported_topics,
        llm_requirements=body.llm_requirements,
        status=body.status,
        registered_at=datetime.now(timezone.utc),
    )
    await registry.register(card)
    return {"status": "registered", "agent_id": body.id}


@router.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str, request: Request):
    _require_scope(request, "agents:write")
    registry = request.app.state.agent_registry
    try:
        await registry.unregister(agent_id)
        return {"status": "unregistered", "agent_id": agent_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")


# ─── Provider management endpoints ───

class ProviderRegisterRequest(BaseModel):
    id: str
    name: str
    url: str
    api_key: str = ""
    models: list[str] = []
    cost_per_input_token: float = 0.0
    cost_per_output_token: float = 0.0
    rate_limit_rpm: int = 1000
    rate_limit_tpm: int = 100000
    priority: int = 1
    weight: float = 1.0


class ProviderUpdateRequest(BaseModel):
    status: str | None = None
    weight: float | None = None
    priority: int | None = None


@router.get("/providers")
async def list_providers(request: Request):
    _require_scope(request, "providers:read")
    balancer = request.app.state.balancer
    circuits = balancer.circuit_states()
    result = []
    for p in balancer.providers:
        healthy = await p.health_check()
        result.append({
            "name": p.name,
            "models": p.models,
            "healthy": healthy,
            "circuit_state": circuits.get(p.name, "unknown"),
        })

    provider_registry = getattr(request.app.state, "provider_registry", None)
    registered = []
    if provider_registry:
        registered = [c.model_dump() for c in provider_registry.get_all()]

    return {"providers": result, "registered": registered}


@router.post("/providers/register")
async def register_provider(body: ProviderRegisterRequest, request: Request):
    _require_scope(request, "providers:write")
    provider_registry = request.app.state.provider_registry
    from src.llm.registry import ProviderConfig
    config = ProviderConfig(**body.model_dump())
    provider_registry.register(config)
    return {"status": "registered", "provider_id": body.id}


@router.delete("/providers/{provider_id}")
async def unregister_provider(provider_id: str, request: Request):
    _require_scope(request, "providers:write")
    provider_registry = request.app.state.provider_registry
    try:
        provider_registry.unregister(provider_id)
        return {"status": "unregistered", "provider_id": provider_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdateRequest, request: Request):
    _require_scope(request, "providers:write")
    provider_registry = request.app.state.provider_registry
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        provider_registry.update(provider_id, updates)
        return {"status": "updated", "provider_id": provider_id}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")


# ─── Auth endpoints ───

class TokenRequest(BaseModel):
    subject: str = "user"
    scopes: list[str] = ["chat:read"]
    expire_seconds: int = 3600


class TokenVerifyRequest(BaseModel):
    token: str


@router.post("/auth/token")
async def create_token(body: TokenRequest):
    """Create a JWT token. In production this would require an admin key."""
    from src.auth.token_auth import token_auth
    try:
        token = token_auth.create_token(
            subject=body.subject,
            scopes=body.scopes,
            expire_seconds=body.expire_seconds,
        )
        return {"token": token, "token_type": "Bearer"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/auth/verify")
async def verify_token(body: TokenVerifyRequest):
    from src.auth.token_auth import token_auth
    try:
        payload = token_auth.verify_token(body.token)
        return {
            "valid": True,
            "subject": payload.sub,
            "scopes": payload.scopes,
            "exp": payload.exp,
        }
    except ValueError as exc:
        return {"valid": False, "detail": str(exc)}


@router.delete("/auth/token/{jti}")
async def revoke_token(jti: str, request: Request):
    _require_scope(request, "admin")
    from src.auth.token_auth import token_auth
    token_auth.revoke_token(jti)
    return {"status": "revoked", "jti": jti}


# ─── Health ───

@router.get("/health")
async def health(request: Request):
    balancer = request.app.state.balancer
    statuses = await balancer.health_check_all()
    all_healthy = all(statuses.values())
    return {
        "status": "ok" if all_healthy else "degraded",
        "providers": statuses,
        "circuit_states": balancer.circuit_states(),
    }
