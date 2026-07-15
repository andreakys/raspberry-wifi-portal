from __future__ import annotations

import logging
import socket
import time
from collections.abc import Callable, Iterable
from threading import Event
from typing import Any


UNAVAILABLE_STATUS_LINE = (
    "internet: no, eth-ip: n/d, eth-mode: n/d, "
    "wi-fi enable: no, wi-fi off"
)


def build_network_status_line(snapshot: dict[str, Any]) -> str:
    interfaces = snapshot.get("interfaces", [])
    if not isinstance(interfaces, list):
        interfaces = []

    ethernet = next(
        (
            item
            for item in interfaces
            if isinstance(item, dict) and item.get("name") == "eth0"
        ),
        {},
    )
    fields = [
        f"internet: {'si' if snapshot.get('internet_available') else 'no'}",
        f"eth-ip: {_first_ip(ethernet)}",
        f"eth-mode: {_ipv4_mode(ethernet.get('ipv4_method'))}",
    ]

    wifi_enabled = bool(snapshot.get("wifi_enabled"))
    fields.append(f"wi-fi enable: {'si' if wifi_enabled else 'no'}")
    if not wifi_enabled:
        fields.append("wi-fi off")
        return ", ".join(fields)

    hotspot_active = bool(snapshot.get("hotspot_active"))
    hotspot_interface = _clean_value(snapshot.get("hotspot_interface"))
    if hotspot_active:
        hotspot_ssid = _clean_value(snapshot.get("hotspot_ssid"))
        portal_address = _clean_value(snapshot.get("portal_address"))
        fields.append(f"hot-spot: {hotspot_ssid} / {portal_address}")

    wifi_interfaces = sorted(
        (
            item
            for item in interfaces
            if isinstance(item, dict) and item.get("type") == "wifi"
        ),
        key=lambda item: str(item.get("name", "")),
    )
    for interface in wifi_interfaces:
        name = _clean_value(interface.get("name"))
        if hotspot_active and name == hotspot_interface:
            continue
        fields.append(
            f"{name}: {_clean_value(interface.get('ssid'))} / {_first_ip(interface)}"
        )

    return ", ".join(fields)


def _first_ip(interface: dict[str, Any]) -> str:
    addresses = interface.get("ipv4_addresses", [])
    if not isinstance(addresses, list) or not addresses:
        return "n/d"
    return _clean_value(str(addresses[0]).split("/", 1)[0])


def _ipv4_mode(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"auto", "dhcp"}:
        return "DHCP"
    if normalized in {"manual", "static"}:
        return "static"
    return "n/d"


def _clean_value(value: object) -> str:
    normalized = " ".join(str(value or "").replace(",", " ").split())
    return normalized or "n/d"


class NetworkStatusTcpServer:
    def __init__(
        self,
        status_provider: Callable[[], str],
        *,
        port: int = 6001,
        interval_seconds: float = 30,
        logger: logging.Logger | None = None,
    ) -> None:
        self.status_provider = status_provider
        self.port = port
        self.interval_seconds = max(0.1, interval_seconds)
        self.logger = logger or logging.getLogger(__name__)
        self.bound_port: int | None = None
        self.ready = Event()

    def serve_forever(self, stop_event: Event | None = None) -> None:
        while not self._stopped(stop_event):
            try:
                self._serve(stop_event)
            except OSError as error:
                self.ready.clear()
                self.logger.error(
                    "Server stato rete TCP non disponibile su 127.0.0.1:%s: %s",
                    self.port,
                    error,
                )
                if stop_event:
                    stop_event.wait(5)
                else:
                    time.sleep(5)

    def _serve(self, stop_event: Event | None) -> None:
        clients: set[socket.socket] = set()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", self.port))
            listener.listen(8)
            listener.settimeout(0.25)
            self.bound_port = int(listener.getsockname()[1])
            self.ready.set()
            self.logger.info(
                "Server stato rete TCP in ascolto su 127.0.0.1:%s",
                self.bound_port,
            )
            next_broadcast: float | None = None

            try:
                while not self._stopped(stop_event):
                    try:
                        client, _ = listener.accept()
                    except socket.timeout:
                        client = None

                    if client is not None:
                        client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        client.settimeout(2)
                        clients.add(client)
                        successful = self._send_current_status([client])
                        if client not in successful:
                            clients.discard(client)
                        if clients and next_broadcast is None:
                            next_broadcast = time.monotonic() + self.interval_seconds

                    now = time.monotonic()
                    if clients and next_broadcast is not None and now >= next_broadcast:
                        clients = self._send_current_status(clients)
                        next_broadcast = (
                            now + self.interval_seconds if clients else None
                        )
            finally:
                self.ready.clear()
                for client in clients:
                    client.close()

    def _send_current_status(
        self, clients: Iterable[socket.socket]
    ) -> set[socket.socket]:
        try:
            status_line = self.status_provider()
        except Exception:
            self.logger.exception("Impossibile comporre lo stato rete TCP")
            status_line = UNAVAILABLE_STATUS_LINE

        payload = f"{status_line}\n".encode("utf-8")
        successful: set[socket.socket] = set()
        for client in clients:
            try:
                client.sendall(payload)
                successful.add(client)
            except OSError:
                client.close()
        return successful

    @staticmethod
    def _stopped(stop_event: Event | None) -> bool:
        return bool(stop_event and stop_event.is_set())
