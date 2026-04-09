from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_port: int = 8000
    log_level: str = "info"

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Mock LLM URLs (comma-separated for multiple instances)
    mock_llm_urls: str = "http://mock-llm-1:8001,http://mock-llm-2:8001,http://mock-llm-3:8001"

    # Balancer
    balancing_strategy: str = "round_robin"

    # Telemetry
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "agent-platform"

    # Prometheus
    prometheus_port: int = 9090

    # MLFlow
    mlflow_tracking_uri: str = "http://mlflow:5000"

    # Agent LLM models
    agent_cheap_model: str = "openai/gpt-4o-mini"
    agent_strong_model: str = "openrouter/deepseek/deepseek-chat-v3-0324"
    agent_max_steps: int = 6
    openrouter_api_key: str = ""

    # Auth
    auth_secret_key: str = "change-me-in-production"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
