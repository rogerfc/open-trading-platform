"""OpenTelemetry metrics for the agent platform."""

import logging
import os

from opentelemetry import metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource


# Module-level state
_initialized = False
_meter = None
_log_handler = None

# Counters
_cycles_total = None
_trades_total = None
_errors_total = None
_actions_total = None


def setup_telemetry() -> bool:
    """Initialize OpenTelemetry metrics.

    Returns True if telemetry was initialized, False if disabled.
    """
    global _initialized, _meter
    global _cycles_total, _trades_total, _errors_total, _actions_total

    if _initialized:
        return True

    # Check if telemetry is enabled
    if os.getenv("OTLP_ENABLED", "true").lower() == "false":
        return False

    # Get configuration from environment
    otlp_endpoint = os.getenv("OTLP_ENDPOINT", "http://localhost:4318/v1/metrics")
    export_interval = int(os.getenv("OTLP_EXPORT_INTERVAL", "5000"))

    # Create resource with service info
    resource = Resource.create({
        "service.name": "agent-platform",
        "service.version": "1.0.0",
    })

    # Create OTLP exporter
    exporter = OTLPMetricExporter(endpoint=otlp_endpoint)

    # Create periodic reader
    reader = PeriodicExportingMetricReader(
        exporter,
        export_interval_millis=export_interval,
    )

    # Set up meter provider
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)

    # Get meter
    _meter = metrics.get_meter("agent_platform", "1.0.0")

    # Create counters
    _cycles_total = _meter.create_counter(
        "agent_cycles_total",
        description="Total number of trading cycles executed",
        unit="1",
    )

    _trades_total = _meter.create_counter(
        "agent_trades_total",
        description="Total number of trades executed by agents",
        unit="1",
    )

    _errors_total = _meter.create_counter(
        "agent_errors_total",
        description="Total number of errors encountered",
        unit="1",
    )

    _actions_total = _meter.create_counter(
        "agent_actions_total",
        description="Total number of actions taken (BUY/SELL/CANCEL)",
        unit="1",
    )

    # === LOGS ===
    global _log_handler
    logs_endpoint = otlp_endpoint.replace("/v1/metrics", "/v1/logs")
    log_exporter = OTLPLogExporter(endpoint=logs_endpoint)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    set_logger_provider(logger_provider)

    _log_handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=logger_provider,
    )

    _initialized = True
    return True


def get_log_handler() -> LoggingHandler | None:
    """Get the OTLP logging handler to attach to Python loggers."""
    return _log_handler


def is_enabled() -> bool:
    """Check if telemetry is initialized and enabled."""
    return _initialized


def record_cycle(agent_name: str, strategy_type: str) -> None:
    """Record a trading cycle completion."""
    if not _initialized:
        return

    attributes = {"agent_name": agent_name, "strategy_type": strategy_type}
    _cycles_total.add(1, attributes)


def record_trade(agent_name: str, strategy_type: str) -> None:
    """Record a trade execution."""
    if not _initialized:
        return

    attributes = {"agent_name": agent_name, "strategy_type": strategy_type}
    _trades_total.add(1, attributes)


def record_error(agent_name: str, error_type: str) -> None:
    """Record an agent error."""
    if not _initialized:
        return

    attributes = {"agent_name": agent_name, "error_type": error_type}
    _errors_total.add(1, attributes)


def record_action(agent_name: str, action_type: str) -> None:
    """Record an agent action (BUY, SELL, CANCEL)."""
    if not _initialized:
        return

    attributes = {"agent_name": agent_name, "action_type": action_type}
    _actions_total.add(1, attributes)
