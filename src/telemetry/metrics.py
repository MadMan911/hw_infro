from opentelemetry import metrics

meter = metrics.get_meter("agent_platform")

# ─── Counters ───
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

llm_input_tokens_total = meter.create_counter(
    name="llm_input_tokens_total",
    description="Total input (prompt) tokens",
    unit="1",
)

llm_output_tokens_total = meter.create_counter(
    name="llm_output_tokens_total",
    description="Total output (completion) tokens",
    unit="1",
)

llm_cost_dollars = meter.create_counter(
    name="llm_request_cost_dollars",
    description="Estimated cost of LLM requests in USD",
    unit="USD",
)

# ─── Histograms ───
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

llm_tpot = meter.create_histogram(
    name="llm_time_per_output_token_seconds",
    description="Average time per output token in seconds",
    unit="s",
)


# ─── Recording helpers ───

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
    llm_input_tokens_total.add(prompt_tokens, {"provider": provider, "model": model})
    llm_output_tokens_total.add(completion_tokens, {"provider": provider, "model": model})


def record_ttft(provider: str, model: str, ttft_s: float) -> None:
    """Record time-to-first-token for a streaming request."""
    llm_ttft.record(ttft_s, {"provider": provider, "model": model})


def record_tpot(provider: str, model: str, tpot_s: float) -> None:
    """Record time-per-output-token for a streaming request."""
    llm_tpot.record(tpot_s, {"provider": provider, "model": model})


def record_cost(provider: str, model: str, cost_usd: float) -> None:
    """Record estimated cost of a request."""
    llm_cost_dollars.add(cost_usd, {"provider": provider, "model": model})
