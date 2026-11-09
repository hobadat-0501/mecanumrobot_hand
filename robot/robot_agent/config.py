"""Robot agent configuration, read from the environment and the repo-root .env file.

Real environment variables win over .env. The link token is mandatory: an empty
ROBOT_LINK_TOKEN refuses to start (SAF-07). Motion is off unless explicitly enabled (SAF-02).
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

# robot/robot_agent/config.py -> repo root (also /opt/mecanum_base on the Jetson).
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "*"})


class ConfigError(ValueError):
    """The configuration is unusable; the agent must not start."""


@dataclass(frozen=True)
class Config:
    motion_enabled: bool
    simulate: bool
    stm_port: str
    stm_baud: int
    lidar_port: str
    lidar_baud: int
    bind_host: str
    bind_port: int
    link_token: str


def _text(env: Mapping[str, str], name: str, default: str) -> str:
    value = env.get(name, "").strip()
    return value if value else default


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name, "").strip().lower()
    if not value:
        return False
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false")


def _integer(env: Mapping[str, str], name: str, default: int, low: int, high: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer") from None
    if not low <= value <= high:
        raise ConfigError(f"{name} must be between {low} and {high}")
    return value


def load_config(
    environ: Mapping[str, str] | None = None, *, env_file: Path | str = ENV_FILE
) -> Config:
    if environ is None:
        file_values = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
        environ = {**file_values, **os.environ}
    token = environ.get("ROBOT_LINK_TOKEN", "").strip()
    if not token:
        raise ConfigError("ROBOT_LINK_TOKEN is empty: refusing to start without a link token")
    host = _text(environ, "ROBOT_BIND_HOST", "127.0.0.1")
    if host in _WILDCARD_HOSTS:
        raise ConfigError("ROBOT_BIND_HOST must be a specific address, not a wildcard")
    return Config(
        motion_enabled=_flag(environ, "ROBOT_MOTION_ENABLED"),
        simulate=_flag(environ, "ROBOT_SIMULATE"),
        stm_port=_text(environ, "STM_PORT", "/dev/rai_controller"),
        stm_baud=_integer(environ, "STM_BAUD", 115200, 1, 4_000_000),
        lidar_port=_text(environ, "LIDAR_PORT", "/dev/rai_lidar"),
        lidar_baud=_integer(environ, "LIDAR_BAUD", 460800, 1, 4_000_000),
        bind_host=host,
        bind_port=_integer(environ, "ROBOT_BIND_PORT", 8765, 1, 65535),
        link_token=token,
    )
