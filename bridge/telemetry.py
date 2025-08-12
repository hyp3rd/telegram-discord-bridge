"""Simple telemetry helpers using Prometheus metrics."""

from prometheus_client import Gauge, CollectorRegistry, generate_latest

registry = CollectorRegistry()

internet_gauge = Gauge(
    "bridge_internet_connected", "Internet connectivity status", registry=registry
)
telegram_gauge = Gauge(
    "bridge_telegram_healthy", "Telegram API health status", registry=registry
)
discord_gauge = Gauge(
    "bridge_discord_healthy", "Discord API health status", registry=registry
)


def update_health_metrics(config) -> None:
    """Update health gauges based on current config."""
    internet_gauge.set(1 if config.application.internet_connected else 0)
    telegram_gauge.set(1 if config.telegram.is_healthy else 0)
    discord_gauge.set(1 if config.discord.is_healthy else 0)


def export_metrics() -> bytes:
    """Return metrics in Prometheus text format."""
    return generate_latest(registry)
