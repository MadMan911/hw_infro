import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from src.config import settings
from src.gateway.middleware import AuthMiddleware, PrometheusMiddleware, metrics_endpoint
from src.gateway.router import router as gateway_router
from src.llm.balancer import BalancingStrategy, LLMBalancer
from src.llm.mock_provider import MockProvider

logger = logging.getLogger(__name__)


class UTF8JSONResponse(JSONResponse):
    """JSONResponse that does not escape non-ASCII characters."""

    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


def _create_providers() -> list:
    """Build provider list from settings."""
    providers = []

    # Mock providers (always available)
    for i, url in enumerate(settings.mock_llm_urls.split(","), start=1):
        url = url.strip()
        if url:
            providers.append(MockProvider(name=f"mock-llm-{i}", base_url=url))

    # OpenAI (only if key is set)
    if settings.openai_api_key:
        from src.llm.openai_provider import OpenAIProvider
        providers.append(OpenAIProvider(api_key=settings.openai_api_key))

    # Anthropic (only if key is set)
    if settings.anthropic_api_key:
        from src.llm.anthropic_provider import AnthropicProvider
        providers.append(AnthropicProvider(api_key=settings.anthropic_api_key))

    return providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    providers = _create_providers()
    strategy = BalancingStrategy(settings.balancing_strategy)
    app.state.balancer = LLMBalancer(providers=providers, strategy=strategy)
    logger.info(
        "Balancer initialized: %d providers, strategy=%s",
        len(providers),
        strategy.value,
    )

    # Setup agents and LangGraph
    try:
        from src.agents.billing_agent import BillingAgent
        from src.agents.diagnostics_agent import DiagnosticsAgent
        from src.agents.faq_agent import FaqAgent
        from src.agents.human_router_agent import HumanRouterAgent
        from src.agents.registry import AgentRegistry
        from src.routing.classifier import RequestClassifier
        from src.routing.graph import build_graph

        registry = AgentRegistry()
        agents = {
            "faq": FaqAgent(model=settings.agent_cheap_model, max_steps=settings.agent_max_steps),
            "diagnostics": DiagnosticsAgent(model=settings.agent_strong_model, max_steps=settings.agent_max_steps),
            "billing": BillingAgent(model=settings.agent_cheap_model, max_steps=settings.agent_max_steps),
            "human_router": HumanRouterAgent(),
        }

        for agent in agents.values():
            await registry.register(agent.card)

        classifier = RequestClassifier(model=settings.agent_cheap_model)
        graph = build_graph(agents, classifier)

        app.state.agent_registry = registry
        app.state.agent_graph = graph
        logger.info("Agent graph initialized: %d agents", len(agents))
    except Exception:
        logger.warning("Agent graph setup failed, /chat will be unavailable", exc_info=True)
        app.state.agent_registry = AgentRegistry()
        app.state.agent_graph = None

    # Setup Provider Registry and wire it into the balancer
    from src.llm.registry import ProviderRegistry
    provider_registry = ProviderRegistry()
    app.state.provider_registry = provider_registry
    app.state.balancer._provider_registry = provider_registry

    # Setup Guardrails
    try:
        from src.guardrails.engine import GuardrailsEngine
        app.state.guardrails = GuardrailsEngine()
        logger.info("Guardrails initialized")
    except Exception:
        logger.warning("Guardrails setup failed", exc_info=True)
        app.state.guardrails = None

    # Auth enabled flag — read from AUTH_ENABLED env var (default: False)
    app.state.auth_enabled = settings.auth_enabled

    # Setup telemetry (non-fatal if collector is not available)
    try:
        from src.telemetry.otel_setup import setup_telemetry
        setup_telemetry(app, settings.otel_service_name, settings.otel_exporter_otlp_endpoint)
    except Exception:
        logger.warning("OTel setup failed, continuing without telemetry")

    # Start balancer background health checks
    await app.state.balancer.start_health_checks(interval=30.0)

    yield

    # Shutdown
    await app.state.balancer.close()
    logger.info("Balancer shut down")


app = FastAPI(
    title="Agent Platform",
    description="Multi-agent tech support platform with LLM balancing",
    version="0.1.0",
    lifespan=lifespan,
    default_response_class=UTF8JSONResponse,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(AuthMiddleware)

# Routes
app.include_router(gateway_router)
app.add_route("/metrics", metrics_endpoint)
