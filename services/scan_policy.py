from __future__ import annotations

from typing import Any


def hotspot_blocks_scan(
    status: dict[str, Any], wifi_interface: str | None = None
) -> bool:
    target_interface = wifi_interface or str(status.get("client_wifi_interface") or "")
    return (
        bool(status.get("hotspot_active"))
        and status.get("hotspot_interface") == target_interface
    )


def can_pause_hotspot_without_losing_page(
    status: dict[str, Any], request_via_hotspot: bool
) -> bool:
    if request_via_hotspot:
        return False

    active_client_interface = status.get("active_client_interface")
    alternate_wifi_path = bool(active_client_interface) and (
        active_client_interface != status.get("hotspot_interface")
    )
    return bool(status.get("lan_connected")) or alternate_wifi_path
