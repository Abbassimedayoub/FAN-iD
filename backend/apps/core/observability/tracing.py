"""
Bootstrap OpenTelemetry (§27/§5.3 Source B).

Instrumentation automatique : Django, psycopg, Redis, requests, Celery.
Appelé une seule fois au démarrage du processus (voir `apps/core/apps.py`
`ready()` — PAS ici au niveau module, pour éviter une double instrumentation
sous le rechargeur de développement Django, qui importe les modules deux fois).
"""

import logging

logger = logging.getLogger("fanid.observability")

_already_instrumented = False


def bootstrap_tracing() -> None:
    global _already_instrumented
    if _already_instrumented:
        return

    import os

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    service_name = os.environ.get("OTEL_SERVICE_NAME", "fanid-api")
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    sample_rate = float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0"))

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(sample_rate)))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)

    DjangoInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    CeleryInstrumentor().instrument()

    _already_instrumented = True
    logger.info("otel_tracing_bootstrapped", extra={"service_name": service_name, "endpoint": endpoint})
