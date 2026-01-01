from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


class ConfigError(RuntimeError):
	"""Raised when configuration cannot be loaded."""


@dataclass(frozen=True)
class DeviceConfig:
	hostname: str
	username: str
	password: str
	name: str


@dataclass(frozen=True)
class ExporterConfig:
	exporter_port: int
	log_level: str
	devices: tuple[DeviceConfig, ...]


_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def load_config(path: str | None) -> ExporterConfig:
	if path:
		data = _load_from_file(path)
	else:
		data = _load_from_env()
	return _build_config(data)


def _load_from_file(path: str) -> dict:
	with Path(path).open("r", encoding="utf-8") as handle:
		loaded = yaml.safe_load(handle)
	if loaded is None:
		msg = f"configuration file '{path}' is empty"
		raise ConfigError(msg)
	return loaded


def _load_from_env() -> dict:
	required = ("FRITZ_USERNAME",)
	if any(not os.getenv(key) for key in required):
		missing = ", ".join(key for key in required if not os.getenv(key))
		msg = f"missing required environment variable(s): {missing}"
		raise ConfigError(msg)
	if not (os.getenv("FRITZ_PASSWORD") or os.getenv("FRITZ_PASSWORD_FILE")):
		msg = "provide FRITZ_PASSWORD or FRITZ_PASSWORD_FILE"
		raise ConfigError(msg)
	device: dict[str, str | None] = {
		"hostname": os.getenv("FRITZ_HOSTNAME", "fritz.box"),
		"username": os.getenv("FRITZ_USERNAME"),
		"password": os.getenv("FRITZ_PASSWORD"),
		"password_file": os.getenv("FRITZ_PASSWORD_FILE"),
		"name": os.getenv("FRITZ_NAME", "Fritz!Box"),
	}
	config: dict[str, object] = {
		"exporter_port": os.getenv("FRITZ_PORT", "18000"),
		"log_level": os.getenv("FRITZ_LOG_LEVEL", "INFO"),
		"devices": [device],
	}
	return config


def _build_config(raw: dict) -> ExporterConfig:
	exporter_port = int(raw.get("exporter_port", 18000))
	log_level = str(raw.get("log_level", "INFO")).upper()
	if log_level not in _LOG_LEVELS:
		log_level = "INFO"
	devices_raw = raw.get("devices", [])
	devices = tuple(_build_device_config(device) for device in _ensure_iterable(devices_raw))
	if not devices:
		raise ConfigError("no devices configured")
	return ExporterConfig(exporter_port, log_level, devices)


def _build_device_config(raw: dict) -> DeviceConfig:
	hostname = str(raw.get("hostname", "fritz.box"))
	username = str(raw.get("username", ""))
	if not username:
		raise ConfigError("device username is required")
	password = _read_password(raw)
	name = str(raw.get("name", hostname))
	return DeviceConfig(hostname=hostname, username=username, password=password, name=name)


def _read_password(raw: dict) -> str:
	password_file = raw.get("password_file")
	if password_file:
		content = Path(str(password_file)).read_text(encoding="utf-8")
		return content.strip()
	password = raw.get("password", "")
	if not password:
		raise ConfigError("device password is required")
	return str(password)


def _ensure_iterable(value: object) -> Iterable[dict]:
	if value is None:
		return ()
	if isinstance(value, dict):
		return (value,)
	if isinstance(value, list | tuple):
		return value  # type: ignore[return-value]
	msg = "devices must be a list"
	raise ConfigError(msg)


def apply_log_level(level: str) -> None:
	logging.getLogger().setLevel(level)
