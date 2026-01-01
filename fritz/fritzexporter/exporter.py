from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzConnectionException,
    FritzServiceError,
)
from prometheus_client.core import (
    CounterMetricFamily,
    GaugeMetricFamily,
)

from .config import DeviceConfig

logger = logging.getLogger("fritzexporter")


@dataclass(frozen=True)
class PPPState:
    value: int
    last_error: str


@dataclass(frozen=True)
class DeviceMetrics:
    dsl_status: int | None
    ppp_state: PPPState | None
    byte_rates: tuple[int, int] | None
    byte_totals: tuple[int, int] | None
    connection_uptime: int | None


class FritzMetricCollector:
    def __init__(self, devices: tuple[DeviceConfig, ...]) -> None:
        self._devices = devices

    def collect(self):
        logger.debug("starting metric collection for %d device(s)", len(self._devices))
        dsl_metric = GaugeMetricFamily(
            "fritz_dsl_status",
            "DSL status (1=up, 0=down)",
            labels=["friendly_name"],
        )
        ppp_metric = GaugeMetricFamily(
            "fritz_ppp_connection_state",
            "PPP connection state (1=connected, 0=disconnected)",
            labels=["friendly_name", "last_error"],
        )
        datarate_metric = GaugeMetricFamily(
            "fritz_wan_datarate_bytes",
            "Current WAN data rate in bytes per second",
            labels=["friendly_name", "direction"],
        )
        data_total_metric = CounterMetricFamily(
            "fritz_wan_data_bytes_total",
            "Total WAN data transferred in bytes",
            labels=["friendly_name", "direction"],
        )
        connection_uptime_seconds_metric = GaugeMetricFamily(
            "fritz_wan_connection_uptime_seconds",
            "Seconds since WAN connection established",
            labels=["friendly_name"],
        )

        for device in self._devices:
            connection = self._connect(device)
            if connection is None:
                logger.warning("skipping device %s - connection unavailable", device.name)
                continue
            collection_start = time.monotonic()
            metrics = _gather_device_metrics(connection)
            collection_ms = (time.monotonic() - collection_start) * 1000.0
            _log_device_metrics(device, metrics, collection_ms)
            if metrics.dsl_status is not None:
                dsl_metric.add_metric([device.name], metrics.dsl_status)
            if metrics.ppp_state is not None:
                ppp_metric.add_metric(
                    [device.name, metrics.ppp_state.last_error],
                    metrics.ppp_state.value,
                )
            if metrics.byte_rates is not None:
                datarate_metric.add_metric([device.name, "rx"], metrics.byte_rates[0])
                datarate_metric.add_metric([device.name, "tx"], metrics.byte_rates[1])
            if metrics.byte_totals is not None:
                data_total_metric.add_metric(
                    [device.name, "rx"], metrics.byte_totals[0]
                )
                data_total_metric.add_metric(
                    [device.name, "tx"], metrics.byte_totals[1]
                )
            if metrics.connection_uptime is not None:
                connection_uptime_seconds_metric.add_metric(
                    [device.name], metrics.connection_uptime
                )

        for metric_family in (
            dsl_metric,
            ppp_metric,
            datarate_metric,
            data_total_metric,
            connection_uptime_seconds_metric,
        ):
            if metric_family.samples:
                yield metric_family

    def _connect(self, device: DeviceConfig) -> FritzConnection | None:
        start = time.monotonic()
        try:
            connection = FritzConnection(
                address=device.hostname,
                user=device.username,
                password=device.password,
            )
            duration_ms = (time.monotonic() - start) * 1000.0
            logger.info(
                "connected to fritz device %s (%s) | connect_ms=%.1f",
                device.name,
                device.hostname,
                duration_ms,
            )
            return connection
        except FritzConnectionException:
            duration_ms = (time.monotonic() - start) * 1000.0
            logger.exception(
                "failed to connect to %s | connect_ms=%.1f",
                device.hostname,
                duration_ms,
            )
            return None


def _log_device_metrics(
    device: DeviceConfig, metrics: DeviceMetrics, collection_ms: float
) -> None:
    missing_fields = []
    if metrics.dsl_status is None:
        missing_fields.append("dsl_status")
    if metrics.ppp_state is None:
        missing_fields.append("ppp_state")
    if metrics.byte_rates is None:
        missing_fields.append("byte_rates")
    if metrics.byte_totals is None:
        missing_fields.append("byte_totals")
    if metrics.connection_uptime is None:
        missing_fields.append("connection_uptime")

    if missing_fields:
        logger.warning(
            "partial metrics collected | device=%s duration_ms=%.1f missing=%s",
            device.name,
            collection_ms,
            ",".join(missing_fields),
        )
    else:
        logger.info(
            "metrics collected | device=%s duration_ms=%.1f",
            device.name,
            collection_ms,
        )

    if metrics.dsl_status == 0:
        logger.warning(
            "dsl reported down | device=%s duration_ms=%.1f",
            device.name,
            collection_ms,
        )

    if metrics.ppp_state is None:
        logger.warning("ppp status unavailable | device=%s", device.name)
    elif metrics.ppp_state.value == 0:
        logger.warning(
            "ppp disconnected | device=%s last_error=%s",
            device.name,
            metrics.ppp_state.last_error,
        )
    elif metrics.ppp_state.last_error and metrics.ppp_state.last_error != "ERROR_NONE":
        logger.info(
            "ppp reported recoverable issue | device=%s last_error=%s",
            device.name,
            metrics.ppp_state.last_error,
        )
def _get_dsl_status(connection: FritzConnection) -> int | None:
    response = _safe_call(connection, "WANDSLInterfaceConfig1", "GetInfo")
    if response is None:
        return None
    return 1 if response.get("NewStatus") == "Up" else 0


def _get_ppp_state(connection: FritzConnection) -> PPPState | None:
    response = _safe_call(connection, "WANPPPConnection1", "GetStatusInfo")
    if response is None:
        return None
    state = 1 if response.get("NewConnectionStatus") == "Connected" else 0
    last_error = response.get("NewLastConnectionError", "")
    return PPPState(state, last_error)


def _get_wan_transfer_metrics(
    connection: FritzConnection,
) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    response = _safe_call(connection, "WANCommonIFC1", "GetAddonInfos")
    if response is None:
        return None, None
    rx_rate = _coerce_int(response.get("NewByteReceiveRate"))
    tx_rate = _coerce_int(response.get("NewByteSendRate"))
    rates = (rx_rate, tx_rate) if rx_rate is not None and tx_rate is not None else None
    rx_total = _coerce_int(response.get("NewTotalBytesReceived"))
    tx_total = _coerce_int(response.get("NewTotalBytesSent"))
    totals = (
        (rx_total, tx_total) if rx_total is not None and tx_total is not None else None
    )
    return rates, totals


def _get_connection_uptime(connection: FritzConnection) -> int | None:
    response = _safe_call(connection, "WANPPPConnection1", "GetInfo")
    if response is None:
        return None
    uptime = _coerce_int(response.get("NewUptime"))
    if uptime is None:
        return None
    return max(uptime, 0)


def _gather_device_metrics(connection: FritzConnection) -> DeviceMetrics:
    connection_uptime = _get_connection_uptime(connection)
    byte_rates, byte_totals = _get_wan_transfer_metrics(connection)
    return DeviceMetrics(
        dsl_status=_get_dsl_status(connection),
        ppp_state=_get_ppp_state(connection),
        byte_rates=byte_rates,
        byte_totals=byte_totals,
        connection_uptime=connection_uptime,
    )


def _safe_call(connection: FritzConnection, service: str, action: str) -> dict | None:
    start = time.monotonic()
    try:
        result = connection.call_action(service, action)
        duration_ms = (time.monotonic() - start) * 1000.0
        logger.debug(
            "%s.%s call succeeded | duration_ms=%.1f",
            service,
            action,
            duration_ms,
        )
        return result
    except (FritzActionError, FritzServiceError, FritzConnectionException) as exc:
        duration_ms = (time.monotonic() - start) * 1000.0
        logger.warning(
            "%s.%s call failed after %.1f ms: %s",
            service,
            action,
            duration_ms,
            exc,
        )
        return None


def _coerce_int(value: int | float | str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
