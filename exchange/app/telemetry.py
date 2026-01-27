"""OpenTelemetry metrics and logs for the stock exchange."""

import logging
import os
from decimal import Decimal

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

# Counters (cumulative)
_trades_total = None
_trade_volume_total = None
_trade_value_total = None
_orders_total = None
_orders_cancelled_total = None
_orders_filled_total = None

# Gauges (current state) - using ObservableGauge with callbacks
_gauge_callbacks = {}


def setup_telemetry() -> bool:
    """Initialize OpenTelemetry metrics.

    Returns True if telemetry was initialized, False if disabled.
    """
    global _initialized, _meter
    global _trades_total, _trade_volume_total, _trade_value_total
    global _orders_total, _orders_cancelled_total, _orders_filled_total

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
        "service.name": "stock-exchange",
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
    _meter = metrics.get_meter("stock_exchange", "1.0.0")

    # Create counters
    _trades_total = _meter.create_counter(
        "exchange_trades_total",
        description="Total number of trades executed",
        unit="1",
    )

    _trade_volume_total = _meter.create_counter(
        "exchange_trade_volume_total",
        description="Total number of shares traded",
        unit="shares",
    )

    _trade_value_total = _meter.create_counter(
        "exchange_trade_value_total",
        description="Total cash value of trades",
        unit="currency",
    )

    _orders_total = _meter.create_counter(
        "exchange_orders_total",
        description="Total number of orders placed",
        unit="1",
    )

    _orders_cancelled_total = _meter.create_counter(
        "exchange_orders_cancelled_total",
        description="Total number of orders cancelled",
        unit="1",
    )

    _orders_filled_total = _meter.create_counter(
        "exchange_orders_filled_total",
        description="Total number of orders fully filled",
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


# --- Counter update functions ---

def record_trade(ticker: str, quantity: int, price: Decimal) -> None:
    """Record a trade execution."""
    if not _initialized:
        return

    attributes = {"ticker": ticker}
    _trades_total.add(1, attributes)
    _trade_volume_total.add(quantity, attributes)
    _trade_value_total.add(float(price * quantity), attributes)


def record_order_placed(ticker: str, side: str, order_type: str) -> None:
    """Record an order being placed."""
    if not _initialized:
        return

    attributes = {"ticker": ticker, "side": side, "type": order_type}
    _orders_total.add(1, attributes)


def record_order_cancelled(ticker: str) -> None:
    """Record an order being cancelled."""
    if not _initialized:
        return

    attributes = {"ticker": ticker}
    _orders_cancelled_total.add(1, attributes)


def record_order_filled(ticker: str) -> None:
    """Record an order being fully filled."""
    if not _initialized:
        return

    attributes = {"ticker": ticker}
    _orders_filled_total.add(1, attributes)


# --- Gauge registration for observable metrics ---

def register_gauge_callback(name: str, callback, description: str, unit: str = "1") -> None:
    """Register a callback for an observable gauge.

    The callback should return an iterable of (value, attributes) tuples.
    """
    if not _initialized or _meter is None:
        return

    if name in _gauge_callbacks:
        return  # Already registered

    def wrapped_callback(options):
        try:
            for value, attrs in callback():
                yield metrics.Observation(value, attrs)
        except Exception:
            pass  # Don't break metrics on callback errors

    _meter.create_observable_gauge(
        name,
        callbacks=[wrapped_callback],
        description=description,
        unit=unit,
    )
    _gauge_callbacks[name] = callback
