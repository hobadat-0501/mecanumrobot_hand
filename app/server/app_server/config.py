"""App server settings, read once from the environment (and `.env` at the repo root)."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]


class ConfigError(ValueError):
    """Raised when the settings are unusable; the server must not start."""


@dataclass(frozen=True)
class Settings:
    robot_ws_url: str
    robot_link_token: str
    operator_token: str
    bind_host: str
    bind_port: int
    allowed_origins: Tuple[str, ...]
    # Calibration: real speed / speed reported by the STM (measured with a tape measure).
    speed_scale: float


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    """Build Settings. With env=None, load `.env` (without overriding) and use os.environ."""
    if env is None:
        load_dotenv(REPO_ROOT / ".env", override=False)
        env = os.environ

    robot_link_token = env.get("ROBOT_LINK_TOKEN", "").strip()
    operator_token = env.get("OPERATOR_TOKEN", "").strip()
    if not robot_link_token:
        raise ConfigError("ROBOT_LINK_TOKEN must not be empty")
    if not operator_token:
        raise ConfigError("OPERATOR_TOKEN must not be empty")

    try:
        bind_port = int(env.get("APP_BIND_PORT", "8000"))
    except ValueError as exc:
        raise ConfigError("APP_BIND_PORT must be an integer") from exc
    if not 1 <= bind_port <= 65535:
        raise ConfigError("APP_BIND_PORT must be in 1..65535")

    try:
        speed_scale = float(env.get("SPEED_SCALE", "1.0"))
    except ValueError as exc:
        raise ConfigError("SPEED_SCALE must be a number") from exc
    if not math.isfinite(speed_scale) or speed_scale <= 0:
        raise ConfigError("SPEED_SCALE must be a finite number greater than 0")

    origins = tuple(
        o.strip()
        for o in env.get("APP_ALLOWED_ORIGINS", "http://100.119.83.63:3000").split(",")
        if o.strip()
    )
    return Settings(
        robot_ws_url=env.get("ROBOT_WS_URL", "ws://100.69.39.18:8765/ws").strip(),
        robot_link_token=robot_link_token,
        operator_token=operator_token,
        bind_host=env.get("APP_BIND_HOST", "100.119.83.63").strip(),
        bind_port=bind_port,
        allowed_origins=origins,
        speed_scale=speed_scale,
    )
