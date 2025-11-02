"""
Purpose:
--------
This service exposes two HTTP endpoints using Flask inside a Linux Docker container:

    /ip       → Returns JSON with current public IPv4, provider, country code, and ping latency.
    /metrics  → Returns the same data in Prometheus exposition format.

Workflow summary:
-----------------
1. Five external providers are used to determine the public IPv4 address:
       ipapi.co, ipwho.is, ifconfig.co, api.ip.sb, ipinfo.io
   The provider list is randomized per request to spread load.

2. Each provider is queried sequentially until one passes **all validation checks**:
       - HTTP status code == 200
       - Content-Type starts with "application/json"
       - Body parses as valid JSON and is a dictionary
       - Contains key "ip"
       - The "ip" value is a valid IPv4 address

3. Once a valid IP is retrieved:
       - The country code (provider-specific key) is extracted and normalized.
       - The service pings that IP using Linux `ping -4 -c 1 -w 2` and extracts latency in ms.
       - If ping fails, latency = 0.0.

4. If all providers fail, the service returns HTTP 502 (no data).

5. Only `flask` and `requests` are required (standard library otherwise).
   The script is IPv4-only, designed for Linux-based Docker environments.
"""

import logging
import random
import requests
import subprocess
import re
import ipaddress
import time
from flask import Flask, jsonify, Response

app = Flask(__name__)
session = requests.Session()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)8s %(name)s | %(message)s",
)
logger = logging.getLogger("ip_exporter")

HTTP_TIMEOUT = 5  # seconds
CACHE_TTL_SECONDS = 30.0

_ip_cache_data = None
_ip_cache_timestamp = 0.0


def is_valid_ipv4(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.version == 4
    except Exception:
        return False


def get_json(provider: str, url: str):
    logger.debug("requesting provider=%s url=%s", provider, url)
    start = time.monotonic()
    try:
        r = session.get(url, timeout=HTTP_TIMEOUT)
        elapsed_ms = (time.monotonic() - start) * 1000.0
        if r.status_code != 200:
            logger.warning(
                "provider=%s unexpected status=%s latency_ms=%.1f",
                provider,
                r.status_code,
                elapsed_ms,
            )
            return None

        if not r.headers.get("Content-Type", "").startswith("application/json"):
            logger.warning(
                "provider=%s returned content-type=%s latency_ms=%.1f",
                provider,
                r.headers.get("Content-Type"),
                elapsed_ms,
            )
            return None

        data = r.json()
        if not isinstance(data, dict):
            logger.warning("provider=%s payload is not a dict", provider)
            return None

        ip = data.get("ip")
        if not isinstance(ip, str) or not is_valid_ipv4(ip):
            logger.warning("provider=%s returned invalid ip=%s", provider, ip)
            return None

        payload_bytes = len(r.content)
        logger.info(
            "provider=%s http_latency_ms=%.1f payload_bytes=%d",
            provider,
            elapsed_ms,
            payload_bytes,
        )
        return data, elapsed_ms, payload_bytes
    except (requests.RequestException, ValueError) as exc:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        logger.warning(
            "provider=%s request failed latency_ms=%.1f error=%s",
            provider,
            elapsed_ms,
            exc,
        )
        return None


def ping_ip(ip: str):
    try:
        out = subprocess.run(
            ["ping", "-4", "-c", "1", "-w", "2", ip],
            capture_output=True,
            text=True,
            timeout=3
        ).stdout
        m = re.search(r"time[=<]?\s*([\d.]+)\s*ms", out)
        if m:
            latency = float(m.group(1))
            logger.info("ping successful ip=%s latency_ms=%.2f", ip, latency)
            return latency
        logger.warning("ping output missing latency ip=%s", ip)
        return None
    except Exception as exc:
        logger.warning("ping failed ip=%s error=%s", ip, exc)
        return None


def fetch_ip_metadata():
    providers = [
        ("ipapi", "https://ipapi.co/json", "country_code"),
        ("ipwhois", "https://ipwho.is/", "country_code"),
        ("ifconfig", "https://ifconfig.co/json", "country_iso"),
        ("ipsb", "https://api.ip.sb/geoip", "country_code"),
    ]

    for attempt, (name, url, code_key) in enumerate(
        random.sample(providers, len(providers)), start=1
    ):
        logger.info("querying provider=%s attempt=%d", name, attempt)
        result = get_json(name, url)
        if not result:
            continue
        j, http_latency_ms, payload_bytes = result
        try:
            ip = j["ip"]
            cc = str(j.get(code_key, "")).upper()
            logger.info(
                "provider=%s success ip=%s country=%s attempt=%d http_latency_ms=%.1f payload_bytes=%d",
                name,
                ip,
                cc,
                attempt,
                http_latency_ms,
                payload_bytes,
            )
            return {
                "provider": name,
                "ip": ip,
                "country_code": cc,
                "http_latency_ms": http_latency_ms,
                "http_payload_bytes": payload_bytes,
                "attempt": attempt,
            }
        except Exception:
            logger.warning("provider=%s response missing required keys", name)
            continue

    logger.error("all providers failed to supply public ip data")
    return {}


def get_ip_data():
    global _ip_cache_data, _ip_cache_timestamp

    now = time.monotonic()
    metadata = None

    cache_hit = False

    if _ip_cache_data and now - _ip_cache_timestamp < CACHE_TTL_SECONDS:
        metadata = dict(_ip_cache_data)
        cache_hit = True
        logger.info(
            "using cached ip metadata provider=%s cache_age_ms=%.1f",
            metadata.get("provider", ""),
            (now - _ip_cache_timestamp) * 1000.0,
        )
    else:
        logger.info("refreshing public ip metadata")
        metadata = fetch_ip_metadata()
        if not metadata:
            logger.error("public ip metadata unavailable")
            return {}
        _ip_cache_data = dict(metadata)
        _ip_cache_timestamp = now

    latency = ping_ip(metadata["ip"])

    logger.info(
        "resolved public ip provider=%s ip=%s ping_ms=%s cache_hit=%s http_latency_ms=%s attempt=%s",
        metadata["provider"],
        metadata["ip"],
        latency if latency is not None else "N/A",
        cache_hit,
        (
            f"{metadata.get('http_latency_ms', 0.0):.1f}"
            if metadata.get("http_latency_ms") is not None
            else "N/A"
        ),
        metadata.get("attempt", "N/A"),
    )

    return {
        "provider": metadata["provider"],
        "ip": metadata["ip"],
        "country_code": metadata["country_code"],
        "ping_ms": latency if latency is not None else 0.0,
    }


@app.get("/ip")
def ip_json():
    data = get_ip_data()
    logger.info("/ip request served success=%s", bool(data))
    return (jsonify(data), 200) if data else (jsonify({}), 502)


@app.get("/metrics")
def metrics():
    data = get_ip_data()
    if not data:
        logger.error("/metrics request failed to obtain ip data")
        return Response("", status=502, mimetype="text/plain")

    logger.info(
        "/metrics request served provider=%s ip=%s", data["provider"], data["ip"]
    )
    lines = [
        "# HELP ip_info Public IP info with ping latency",
        "# TYPE ip_info gauge",
        f'ip_info{{provider="{data["provider"]}",country_code="{data["country_code"]}"}} {data["ping_ms"]}',
        "",
        "# HELP ip_current_info Current public IP as text in label, stable series",
        "# TYPE ip_current_info gauge",
        f'ip_current_info{{label="ip_address",value="{data["ip"]}"}} 1'
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=18002)
