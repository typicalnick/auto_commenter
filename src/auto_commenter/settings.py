from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class ChannelConfig:
    """Configuration describing how to react to messages in a channel."""

    source: str
    send_as: str
    templates: List[str]


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session_name: str
    db_path: Path
    min_days_between_comments: int
    template_cooldown_days: int
    channel_configs: List[ChannelConfig]


class SettingsError(RuntimeError):
    """Raised when a mandatory configuration value is missing."""


DEFAULT_CHANNEL_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "channels.json"
_settings_cache: Optional[Settings] = None


def _load_channel_configs(path: Path) -> List[ChannelConfig]:
    if not path.exists():
        raise SettingsError(
            "Channel configuration file not found. "
            "Create config/channels.json (or override CHANNEL_CONFIG_PATH) "
            "using config/channels.example.json as a template."
        )

    with path.open("r", encoding="utf-8") as fp:
        try:
            raw_configs = json.load(fp)
        except json.JSONDecodeError as exc:
            raise SettingsError(f"Failed to parse channel configuration: {exc}") from exc

    if not isinstance(raw_configs, list):
        raise SettingsError("Channel configuration must be a list of objects.")

    configs: List[ChannelConfig] = []
    for entry in raw_configs:
        if not isinstance(entry, dict):
            raise SettingsError("Each channel configuration must be an object.")
        try:
            configs.append(
                ChannelConfig(
                    source=entry["source"],
                    send_as=entry["send_as"],
                    templates=list(entry["templates"]),
                )
            )
        except KeyError as exc:
            raise SettingsError(
                "Each channel configuration requires 'source', 'send_as' and 'templates'."
            ) from exc
    return configs


def load_settings() -> Settings:
    load_dotenv()

    api_id_raw = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "auto_commenter")
    db_path_raw = os.getenv("AUTO_COMMENTER_DB_PATH", "data/comments.db")
    min_days_between_comments = int(os.getenv("MIN_DAYS_BETWEEN_COMMENTS", "7"))
    template_cooldown_days = int(os.getenv("TEMPLATE_COOLDOWN_DAYS", "45"))
    channel_config_path = Path(
        os.getenv("CHANNEL_CONFIG_PATH", DEFAULT_CHANNEL_CONFIG_PATH)
    )

    if not api_id_raw or not api_hash:
        raise SettingsError(
            "TELEGRAM_API_ID and TELEGRAM_API_HASH must be provided in the environment."
        )

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise SettingsError("TELEGRAM_API_ID must be an integer") from exc

    channel_configs = _load_channel_configs(channel_config_path)

    db_path = Path(db_path_raw)
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        session_name=session_name,
        db_path=db_path,
        min_days_between_comments=min_days_between_comments,
        template_cooldown_days=template_cooldown_days,
        channel_configs=channel_configs,
    )


def get_settings(force_reload: bool = False) -> Settings:
    global _settings_cache
    if force_reload or _settings_cache is None:
        _settings_cache = load_settings()
    return _settings_cache


__all__ = [
    "ChannelConfig",
    "Settings",
    "SettingsError",
    "DEFAULT_CHANNEL_CONFIG_PATH",
    "get_settings",
]
