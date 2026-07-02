from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_from_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PortalConfig:
    host: str = os.getenv("PORTAL_HOST", "0.0.0.0")
    port: int = int(os.getenv("PORTAL_PORT", "80"))
    debug: bool = _bool_from_env("PORTAL_DEBUG", False)
    wifi_interface: str = os.getenv("WIFI_INTERFACE", "wlan0")
    hotspot_interface: str = os.getenv("HOTSPOT_INTERFACE", os.getenv("WIFI_INTERFACE", "wlan0"))
    client_wifi_interface: str = os.getenv("CLIENT_WIFI_INTERFACE", os.getenv("WIFI_INTERFACE", "wlan0"))
    hotspot_connection_name: str = os.getenv("HOTSPOT_CONNECTION_NAME", "Pi Setup AP")
    hotspot_ssid: str = os.getenv("HOTSPOT_SSID", "Pi-Setup")
    hotspot_password: str = os.getenv("HOTSPOT_PASSWORD", "ChangeMe123!")
    hotspot_address: str = os.getenv("HOTSPOT_ADDRESS", "192.168.4.1/24")
    connection_wait_seconds: int = int(os.getenv("CONNECTION_WAIT_SECONDS", "45"))
    portal_title: str = os.getenv("PORTAL_TITLE", "Raspberry Pi Wi-Fi Setup")
    auto_recovery_enabled: bool = _bool_from_env("AUTO_RECOVERY_ENABLED", True)
    recovery_check_interval_seconds: int = int(os.getenv("RECOVERY_CHECK_INTERVAL_SECONDS", "5"))
    boot_connection_grace_seconds: int = int(os.getenv("BOOT_CONNECTION_GRACE_SECONDS", "75"))
    reconnect_grace_seconds: int = int(os.getenv("RECONNECT_GRACE_SECONDS", "45"))
    disconnect_hotspot_threshold_seconds: int = int(os.getenv("DISCONNECT_HOTSPOT_THRESHOLD_SECONDS", "180"))
    hotspot_cooldown_seconds: int = int(os.getenv("HOTSPOT_COOLDOWN_SECONDS", "90"))


def load_config() -> PortalConfig:
    return PortalConfig()
