import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentCallMetrics:
    agent_id: str
    model: str
    ttft: float = 0.0       # time to first token (seconds)
    tpot: float = 0.0       # time per output token (seconds)
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency: float = 0.0    # total latency (seconds)
    steps: int = 0
    escalated: bool = False


class MLFlowTracer:
    """Logs agent calls to MLFlow as runs with params and metrics."""

    def __init__(self, tracking_uri: str = "") -> None:
        self._enabled = False
        self._tracking_uri = tracking_uri
        try:
            import mlflow
            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment("agent_platform")
            self._mlflow = mlflow
            self._enabled = True
            logger.info("MLFlow tracer initialized, tracking_uri=%s", tracking_uri or "default")
        except Exception as exc:
            logger.warning("MLFlow not available, tracing disabled: %s", exc)

    async def trace_agent_call(
        self,
        request_message: str,
        response_content: str,
        metrics: AgentCallMetrics,
    ) -> None:
        """Log one agent invocation to MLFlow as a run."""
        if not self._enabled:
            return
        try:
            mlflow = self._mlflow
            with mlflow.start_run(run_name=f"agent_{metrics.agent_id}"):
                # Parameters (categorical / string)
                mlflow.log_param("agent_id", metrics.agent_id)
                mlflow.log_param("model", metrics.model)
                mlflow.log_param("escalated", metrics.escalated)
                mlflow.log_param("steps", metrics.steps)

                # Metrics (numeric)
                mlflow.log_metric("ttft_seconds", metrics.ttft)
                mlflow.log_metric("tpot_seconds", metrics.tpot)
                mlflow.log_metric("total_tokens", metrics.total_tokens)
                mlflow.log_metric("input_tokens", metrics.input_tokens)
                mlflow.log_metric("output_tokens", metrics.output_tokens)
                mlflow.log_metric("cost_dollars", metrics.cost)
                mlflow.log_metric("latency_seconds", metrics.latency)

                # Artifacts: request / response text
                mlflow.log_text(request_message[:2000], "request.txt")
                mlflow.log_text(response_content[:2000], "response.txt")
        except Exception as exc:
            logger.debug("MLFlow logging failed (non-fatal): %s", exc)


# Singleton
_tracer: MLFlowTracer | None = None


def get_tracer() -> MLFlowTracer:
    global _tracer
    if _tracer is None:
        from src.config import settings
        _tracer = MLFlowTracer(tracking_uri=settings.mlflow_tracking_uri)
    return _tracer
