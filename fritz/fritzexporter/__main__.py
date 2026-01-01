from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from prometheus_client import CollectorRegistry, start_http_server

from . import __version__
from .config import ConfigError, apply_log_level, load_config
from .exporter import FritzMetricCollector


_DEFAULT_CONFIG_PATH = Path("/etc/fritz/fritz.yml")
_LISTEN_ADDRESS = "0.0.0.0"


def _resolve_config_path(arg: str | None) -> str | None:
	if arg:
		candidate = Path(arg)
		if candidate.is_file():
			return str(candidate)
		msg = f"configuration file '{arg}' not found"
		raise ConfigError(msg)
	if _DEFAULT_CONFIG_PATH.is_file():
		return str(_DEFAULT_CONFIG_PATH)
	return None


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=f"Minimal Fritz!Box exporter (v{__version__})",
	)
	parser.add_argument("--config", help=f"Path to YAML configuration file (defaults to {_DEFAULT_CONFIG_PATH})")
	parser.add_argument(
		"--log-level",
		choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
		help="Override configured log level",
	)
	return parser.parse_args()


def main() -> None:
	logging.basicConfig(
		level=logging.INFO,
		format="%(asctime)s %(levelname)8s %(name)s | %(message)s",
	)
	logger = logging.getLogger("fritzexporter")
	args = parse_args()
	try:
		config_path = _resolve_config_path(args.config)
		config = load_config(config_path)
	except ConfigError as exc:
		logger.error("configuration error: %s", exc)
		sys.exit(1)
	level = args.log_level or config.log_level
	apply_log_level(level)
	registry = CollectorRegistry()
	registry.register(FritzMetricCollector(config.devices))
	logger.info("starting exporter on %s:%s", _LISTEN_ADDRESS, config.exporter_port)
	start_http_server(config.exporter_port, _LISTEN_ADDRESS, registry)
	try:
		while True:
			time.sleep(60)
	except KeyboardInterrupt:
		logger.info("shutting down")


if __name__ == "__main__":
	main()
