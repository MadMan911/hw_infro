from opentelemetry import metrics

meter = metrics.get_meter("agent_platform")

# Counters
llm_requests_total = meter.create_counter(
    name="llm_requests_total",
    description="Total number of LLM requests",
    unit="1",
)

llm_request_errors_total = meter.create_counter(
    name="llm_request_errors_total",
    description="Total number of LLM request errors",
    unit="1",
)

llm_tokens_total = meter.create_counter(
    name="llm_tokens_total",
    description="Total tokens consumed",
    unit="1",
)

# Histograms
llm_request_duration = meter.create_histogram(
    name="llm_request_duration_seconds",
    description="LLM request latency in seconds",
    unit="s",
)

llm_ttft = meter.create_histogram(
    name="llm_time_to_first_token_seconds",
    description="Time to first token in seconds",
    unit="s",
)


def record_llm_request(provider: str, model: str, status: str, duration_s: float) -> None:
    labels = {"provider": provider, "model": model, "status": status}
    llm_requests_total.add(1, labels)
    llm_request_duration.record(duration_s, labels)


def record_llm_error(provider: str, error_type: str) -> None:
    llm_request_errors_total.add(1, {"provider": provider, "error_type": error_type})


def record_tokens(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    llm_tokens_total.add(prompt_tokens, {"provider": provider, "model": model, "type": "prompt"})
    llm_tokens_total.add(
        completion_tokens, {"provider": provider, "model": model, "type": "completion"}
    )
