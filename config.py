from __future__ import annotations

import os
from dataclasses import dataclass

APP_VERSION = "1.13.0"
DEFAULT_PORTAL_TITLE = "VT Network Manager"


def _bool_from_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value


@dataclass(frozen=True)
class PortalConfig:
    host: str = _env("PORTAL_HOST", "0.0.0.0")
    port: int = int(os.getenv("PORTAL_PORT", "80"))
    debug: bool = _bool_from_env("PORTAL_DEBUG", False)
    wifi_interface: str = _env("WIFI_INTERFACE", "wlan0")
    hotspot_interface: str = _env("HOTSPOT_INTERFACE", _env("WIFI_INTERFACE", "wlan0"))
    client_wifi_interface: str = _env("CLIENT_WIFI_INTERFACE", _env("WIFI_INTERFACE", "wlan0"))
    hotspot_connection_name: str = _env("HOTSPOT_CONNECTION_NAME", "Pi Setup AP")
    hotspot_ssid: str = _env("HOTSPOT_SSID", "Pi-Setup")
    hotspot_password: str = _env("HOTSPOT_PASSWORD", "ChangeMe123!")
    portal_password: str = _env("PORTAL_PASSWORD", _env("HOTSPOT_PASSWORD", "ChangeMe123!"))
    portal_session_secret: str = _env(
        "PORTAL_SESSION_SECRET",
        _env("PORTAL_PASSWORD", _env("HOTSPOT_PASSWORD", "ChangeMe123!")),
    )
    hotspot_address: str = _env("HOTSPOT_ADDRESS", "192.168.4.1/24")
    connection_wait_seconds: int = int(os.getenv("CONNECTION_WAIT_SECONDS", "45"))
    portal_title: str = _env("PORTAL_TITLE", DEFAULT_PORTAL_TITLE)
    app_version: str = _env("APP_VERSION", APP_VERSION)
    auto_recovery_enabled: bool = _bool_from_env("AUTO_RECOVERY_ENABLED", True)
    recovery_check_interval_seconds: int = int(os.getenv("RECOVERY_CHECK_INTERVAL_SECONDS", "5"))
    boot_connection_grace_seconds: int = int(os.getenv("BOOT_CONNECTION_GRACE_SECONDS", "75"))
    reconnect_grace_seconds: int = int(os.getenv("RECONNECT_GRACE_SECONDS", "45"))
    disconnect_hotspot_threshold_seconds: int = int(os.getenv("DISCONNECT_HOTSPOT_THRESHOLD_SECONDS", "180"))
    hotspot_cooldown_seconds: int = int(os.getenv("HOTSPOT_COOLDOWN_SECONDS", "90"))


def load_config() -> PortalConfig:
    return PortalConfig()
