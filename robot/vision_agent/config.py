"""Vision agent configuration (env + repo-root .env). The link token is mandatory (SAF-07)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})
_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", "*"})


class ConfigError(ValueError):
    """The configuration is unusable; the agent must not start."""


@dataclass(frozen=True)
class Config:
    simulate: bool
    bind_host: str
    bind_port: int
    link_token: str
    robot_socket: str = "/run/mecanum/vision.sock"
    own_socket: str = "/run/mecanum/vision-agent.sock"
    db_path: str = "data/vision/staff.sqlite3"
    face_key: str = ""  # Fernet key; empty = key file next to the database


def _flag(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name, "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false")


def load_config(
    environ: Mapping[str, str] | None = None, *, env_file: Path | str = ENV_FILE
) -> Config:
    if environ is None:
        values = dotenv_values(env_file) if Path(env_file).exists() else {}
        environ = {**{k: v for k, v in values.items() if v is not None}, **os.environ}
    token = environ.get("VISION_LINK_TOKEN", "").strip()
    if not token:
        raise ConfigError("VISION_LINK_TOKEN must not be empty")
    host = environ.get("VISION_BIND_HOST", "").strip() or "127.0.0.1"
    if host in _WILDCARD_HOSTS:
        raise ConfigError("VISION_BIND_HOST must be a specific address, not a wildcard")
    try:
        port = int(environ.get("VISION_BIND_PORT", "").strip() or "8766")
    except ValueError as exc:
        raise ConfigError("VISION_BIND_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ConfigError("VISION_BIND_PORT out of range")
    return Config(
        simulate=_flag(environ, "VISION_SIMULATE"),
        bind_host=host,
        bind_port=port,
        link_token=token,
        robot_socket=environ.get("VISION_SOCKET", "").strip() or "/run/mecanum/vision.sock",
        own_socket=environ.get("VISION_OWN_SOCKET", "").strip()
        or "/run/mecanum/vision-agent.sock",
        db_path=environ.get("VISION_DB", "").strip() or "data/vision/staff.sqlite3",
        face_key=environ.get("FACE_DATA_KEY", "").strip(),
    )
