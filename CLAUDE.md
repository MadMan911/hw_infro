# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent tech support platform (Russian: "Мультиагентная платформа техподдержки"). The platform registers A2A agents, connects multiple LLM providers, routes requests intelligently, and collects telemetry. Built as a university assignment with 3 levels of complexity.

**Stack:** Python 3.11+, FastAPI, httpx (async), Docker Compose, OpenTelemetry, Prometheus, Grafana, MLFlow, Locust.

## Architecture

- **API Gateway** (`src/gateway/`) — FastAPI entry point with auth, guardrails, and OTel middleware
- **Request Router** (`src/routing/classifier.py`) — classifies user queries (FAQ/diagnostics/billing/escalation) via LLM or keyword rules
- **Agent Registry** (`src/agents/registry.py`) — stores Agent Cards, finds agents by method/topic
- **Agents** (`src/agents/`) — FAQ, Diagnostics, Billing, Human Router; each extends `BaseAgent`
- **LLM Balancer** (`src/llm/balancer.py`) — proxy that routes LLM calls with strategies: round-robin, weighted, latency-based, health-aware
- **Provider Registry** (`src/llm/registry.py`) — dynamic registration of LLM providers with cost/limits/priority
- **Guardrails** (`src/guardrails/`) — pipeline: prompt injection detection, PII filter, secret detector
- **Auth** (`src/auth/`) — JWT token-based authorization with scopes
- **Telemetry** (`src/telemetry/`) — OTel setup, custom metrics (TTFT, TPOT, cost), MLFlow tracing

Request flow: Client → Auth → Guardrails(input) → Classifier → Agent Registry → Agent → LLM Balancer → Provider → Guardrails(output) → Response

## Commands

```bash
# Run everything
docker-compose up --build

# Run app locally (dev)
uvicorn src.main:app --reload --port 8000

# Tests
pytest
pytest tests/test_balancer.py -v          # single test file
pytest tests/test_balancer.py::test_name  # single test

# Load tests
locust -f load_tests/locustfile.py --host=http://localhost:8000

# Linting (if configured)
ruff check src/
ruff format src/
```

## Key Design Decisions

- LLM providers implement `BaseLLMProvider` ABC with `chat_completion(stream=True/False)` and `health_check()`
- Streaming uses SSE throughout — balancer proxies token-by-token, never buffers full response
- Mock LLM server (`mock_llm_server/`) mimics OpenAI Chat Completions API with configurable latency and error rate
- Health-aware routing uses circuit breaker pattern (CLOSED → OPEN → HALF-OPEN)
- All agents declare their LLM preferences (model, max_tokens, cost) in their Agent Card
- Guardrails run as a pipeline on both input and output

## Docker Services

`app` (port 8000), `mock-llm-1/2/3` (configurable latency/errors), `prometheus` (9090), `grafana` (3000), `mlflow` (5000), `otel-collector` (4317/4318)
