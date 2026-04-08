import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)


def setup_telemetry(app, service_name: str, otlp_endpoint: str) -> None:
    """Initialize OpenTelemetry tracing and metrics, instrument FastAPI."""
    resource = Resource.create({"service.name": service_name})

    # --- Tracing ---
    tracer_provider = TracerProvider(resource=resource)
    try:
        span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    except Exception:
        logger.warning("Could not connect OTLP span exporter, tracing disabled")
    trace.set_tracer_provider(tracer_provider)

    # --- Metrics ---
    try:
        metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
    except Exception:
        logger.warning("Could not connect OTLP metric exporter, metrics disabled")

    # --- Instrument FastAPI ---
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry initialized: service=%s, endpoint=%s", service_name, otlp_endpoint)
