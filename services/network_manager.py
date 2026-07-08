from __future__ import annotations

import ipaddress
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import PortalConfig


class NetworkManagerError(RuntimeError):
    """Raised when a NetworkManager command fails."""

    def __init__(self, message: str, *, stderr: str = "", stdout: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr
        self.stdout = stdout


@dataclass
class ConfigureResult:
    success: bool
    message: str
    connection_name: str | None = None
    connectivity: str | None = None


CONNECTED_CONNECTIVITY_STATES = {"connected", "connected (site only)", "full", "limited", "portal"}
CONNECTING_DEVICE_STATES = {"prepare", "config", "ip-config", "ip-check", "secondaries", "connecting"}
CONNECTED_DEVICE_STATES = {"connected", "activated"}
DISCONNECTED_DEVICE_STATES = {"disconnected", "unavailable", "failed", "deactivating"}
WIFI_CONNECTION_TYPES = {"wifi", "802-11-wireless", "wireless"}


class NetworkManagerService:
    def __init__(self, config: PortalConfig) -> None:
        self.config = config

    def _run_nmcli(self, *args: str, check: bool = True, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["nmcli", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if check and completed.returncode != 0:
            raise NetworkManagerError(
                f"nmcli command failed: {' '.join(args)}",
                stderr=completed.stderr.strip(),
                stdout=completed.stdout.strip(),
            )

        return completed

    def ensure_wifi_enabled(self) -> None:
        self._run_nmcli("radio", "wifi", "on")

    def connectivity(self) -> str:
        result = self._run_nmcli("-t", "-g", "STATE", "general", "status")
        status = result.stdout.strip().lower()
        return status or "unknown"

    def hotspot_active(self) -> bool:
        result = self._run_nmcli("-t", "-f", "NAME,TYPE", "connection", "show", "--active")
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            name, _, connection_type = line.partition(":")
            if name == self.config.hotspot_connection_name and self._is_wifi_connection_type(connection_type):
                return True
        return self.active_connection_name_for_device(self.config.hotspot_interface) == self.config.hotspot_connection_name

    def _is_wifi_connection_type(self, connection_type: str) -> bool:
        return connection_type.strip().lower() in WIFI_CONNECTION_TYPES

    def active_connection_name(self) -> str | None:
        return self.active_connection_name_for_device(self.config.client_wifi_interface)

    def active_connection_name_for_device(self, interface: str) -> str | None:
        result = self._run_nmcli("-t", "-f", "DEVICE,STATE,CONNECTION", "device", "status")
        for line in result.stdout.splitlines():
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            device, state, connection = parts
            if device == interface and state in {"connected", "connecting"}:
                return connection or None
        return None

    def device_state(self) -> str:
        result = self._run_nmcli("-t", "-f", "DEVICE,STATE", "device", "status")
        for line in result.stdout.splitlines():
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            device, state = parts
            if device == self.config.client_wifi_interface:
                return state.strip().lower() or "unknown"
        return "unknown"

    def active_client_connection_name(self) -> str | None:
        connection_name = self.active_connection_name()
        if connection_name == self.config.hotspot_connection_name:
            return None
        return connection_name

    def current_status(self) -> dict[str, Any]:
        interfaces = self.list_ip_interfaces()
        wifi_interfaces = self._wifi_interfaces(interfaces)
        return {
            "wifi_interface": self.config.wifi_interface,
            "hotspot_interface": self.config.hotspot_interface,
            "client_wifi_interface": self.config.client_wifi_interface,
            "wifi_interfaces": wifi_interfaces,
            "wifi_interface_names": [item["name"] for item in wifi_interfaces],
            "wifi_interface_count": len(wifi_interfaces),
            "has_separate_wifi_interfaces": self.config.hotspot_interface != self.config.client_wifi_interface,
            "board_temperature": self.board_temperature(),
            "connectivity": self.connectivity(),
            "device_state": self.device_state(),
            "active_connection": self.active_connection_name(),
            "active_client_connection": self.active_client_connection_name(),
            "wifi_client_configured": self.wifi_client_configured(),
            "hotspot_active": self.hotspot_active(),
            "hotspot_ssid": self.config.hotspot_ssid,
            "portal_address": self.config.hotspot_address.split("/", 1)[0],
            "lan_connected": self._lan_connected(interfaces),
            "lan_interfaces": self._lan_interfaces(interfaces),
            "interfaces": interfaces,
        }

    def wifi_client_configured(self) -> bool:
        result = self._run_nmcli("-t", "-f", "NAME,TYPE", "connection", "show", check=False)
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            name, _, connection_type = line.partition(":")
            if self._is_wifi_connection_type(connection_type) and name != self.config.hotspot_connection_name:
                return True
        return False

    def board_temperature(self) -> dict[str, Any]:
        celsius = self._read_board_temperature_celsius()
        return {
            "celsius": celsius,
            "display": f"{celsius:.1f} C" if celsius is not None else "n/d",
        }

    def reboot_system(self) -> None:
        try:
            subprocess.Popen(["systemctl", "reboot"])
        except OSError as error:
            raise NetworkManagerError(f"Riavvio non riuscito: {error}") from error

    def list_ip_interfaces(self) -> list[dict[str, Any]]:
        result = self._run_nmcli("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status")
        interfaces: list[dict[str, Any]] = []
        hotspot_is_active = self.hotspot_active()

        for line in result.stdout.splitlines():
            if not line.strip():
                continue

            parts = line.split(":", 3)
            if len(parts) != 4:
                continue

            device, device_type, state, connection = parts
            if device in {"lo", ""} or device_type not in {"ethernet", "wifi"}:
                continue

            connection_name = connection if connection and connection != "--" else None
            is_hotspot_interface = (
                device == self.config.hotspot_interface
                and connection_name == self.config.hotspot_connection_name
                and hotspot_is_active
            )

            interfaces.append(
                {
                    "name": device,
                    "type": device_type,
                    "state": state,
                    "connection": connection_name,
                    "ipv4_addresses": self._device_values(device, "IP4.ADDRESS"),
                    "gateway": self._first_device_value(device, "IP4.GATEWAY"),
                    "dns": self._device_values(device, "IP4.DNS"),
                    "ipv4_method": self._connection_ipv4_method(connection_name),
                    "configurable": not is_hotspot_interface,
                    "protected_reason": "hotspot-attivo" if is_hotspot_interface else None,
                }
            )

        return interfaces

    def _lan_connected(self, interfaces: list[dict[str, Any]]) -> bool:
        return any(
            item.get("type") == "ethernet"
            and item.get("state") == "connected"
            and bool(item.get("ipv4_addresses"))
            for item in interfaces
        )

    def _lan_interfaces(self, interfaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in interfaces if item.get("type") == "ethernet"]

    def _wifi_interfaces(self, interfaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in interfaces if item.get("type") == "wifi"]

    def _read_board_temperature_celsius(self) -> float | None:
        thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
        try:
            raw_value = thermal_path.read_text(encoding="utf-8").strip()
            return int(raw_value) / 1000
        except (OSError, ValueError):
            return None

    def configure_interface_ipv4(self, payload: dict[str, str]) -> str:
        interface = payload.get("interface", "").strip()
        mode = payload.get("ip_mode", "").strip().lower()
        address = payload.get("ip_address", "").strip()
        gateway = payload.get("gateway", "").strip()
        dns = payload.get("dns", "").strip()

        validation_error = self.validate_interface_ipv4_configuration(payload)
        if validation_error:
            raise NetworkManagerError(validation_error)

        connection_name = self._connection_for_interface(interface)

        if mode == "dhcp":
            self._run_nmcli(
                "connection",
                "modify",
                connection_name,
                "ipv4.method",
                "auto",
                "ipv4.addresses",
                "",
                "ipv4.gateway",
                "",
                "ipv4.dns",
                "",
                "connection.autoconnect",
                "yes",
            )
        else:
            args = [
                "connection",
                "modify",
                connection_name,
                "ipv4.method",
                "manual",
                "ipv4.addresses",
                address,
                "ipv4.gateway",
                gateway,
                "ipv4.dns",
                self._normalize_dns(dns),
                "connection.autoconnect",
                "yes",
            ]
            self._run_nmcli(*args)

        self._run_nmcli("connection", "up", connection_name, "ifname", interface, timeout=self.config.connection_wait_seconds)
        return connection_name

    def validate_interface_ipv4_configuration(self, payload: dict[str, str]) -> str | None:
        interface = payload.get("interface", "").strip()
        mode = payload.get("ip_mode", "").strip().lower()
        address = payload.get("ip_address", "").strip()
        gateway = payload.get("gateway", "").strip()
        dns = payload.get("dns", "").strip()

        interfaces = {item["name"]: item for item in self.list_ip_interfaces()}
        selected = interfaces.get(interface)
        if not selected:
            return "Seleziona un'interfaccia di rete valida."

        if not selected.get("configurable"):
            return "L'interfaccia dell'hotspot attivo non puo' essere modificata dal portale."

        if mode not in {"dhcp", "static"}:
            return "Seleziona DHCP oppure indirizzo statico."

        if mode == "dhcp":
            return None

        if not address:
            return "Per l'indirizzo statico serve un IPv4 con prefisso, ad esempio 192.168.1.50/24."

        try:
            parsed_address = ipaddress.ip_interface(address)
        except ValueError:
            return "Indirizzo IPv4 statico non valido. Usa il formato 192.168.1.50/24."

        if parsed_address.version != 4:
            return "Sono supportati solo indirizzi IPv4."

        if gateway:
            try:
                parsed_gateway = ipaddress.ip_address(gateway)
            except ValueError:
                return "Gateway IPv4 non valido."
            if parsed_gateway.version != 4:
                return "Il gateway deve essere IPv4."

        for dns_server in self._split_dns(dns):
            try:
                parsed_dns = ipaddress.ip_address(dns_server)
            except ValueError:
                return f"DNS IPv4 non valido: {dns_server}"
            if parsed_dns.version != 4:
                return "I server DNS devono essere IPv4."

        return None

    def list_networks(self) -> list[dict[str, str]]:
        result = self._run_nmcli(
            "--mode",
            "multiline",
            "--fields",
            "IN-USE,SSID,BSSID,SIGNAL,SECURITY,CHAN,FREQ",
            "device",
            "wifi",
            "list",
            "ifname",
            self.config.client_wifi_interface,
            "--rescan",
            "yes",
        )

        networks: list[dict[str, str]] = []
        current: dict[str, str] = {}

        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                if current.get("ssid"):
                    networks.append(current)
                current = {}
                continue

            key, _, value = line.partition(":")
            normalized_key = key.strip().lower().replace("-", "_")
            if normalized_key == "in_use" and current:
                if current.get("ssid"):
                    networks.append(current)
                current = {}
            current[normalized_key] = value.strip()

        if current.get("ssid"):
            networks.append(current)

        visible_networks = [network for network in networks if network.get("ssid", "")]
        return sorted(
            visible_networks,
            key=lambda network: self._network_signal_value(network),
            reverse=True,
        )

    def _network_signal_value(self, network: dict[str, str]) -> int:
        signal = network.get("signal", "").strip()
        return int(signal) if signal.isdigit() else 0

    def ensure_hotspot(self) -> None:
        self.ensure_wifi_enabled()

        if not self._connection_exists(self.config.hotspot_connection_name):
            self._run_nmcli(
                "connection",
                "add",
                "type",
                "wifi",
                "ifname",
                self.config.hotspot_interface,
                "con-name",
                self.config.hotspot_connection_name,
                "ssid",
                self.config.hotspot_ssid,
            )

        self._run_nmcli(
            "connection",
            "modify",
            self.config.hotspot_connection_name,
            "802-11-wireless.mode",
            "ap",
            "802-11-wireless.band",
            "bg",
            "802-11-wireless.hidden",
            "no",
            "ipv4.method",
            "shared",
            "ipv4.addresses",
            self.config.hotspot_address,
            "ipv6.method",
            "ignore",
            "wifi-sec.key-mgmt",
            "wpa-psk",
            "wifi-sec.psk",
            self.config.hotspot_password,
            "connection.autoconnect",
            "no",
        )

        self._run_nmcli(
            "connection",
            "up",
            self.config.hotspot_connection_name,
            "ifname",
            self.config.hotspot_interface,
            timeout=self.config.connection_wait_seconds,
        )

    def stop_hotspot(self) -> None:
        if self.hotspot_active():
            self._run_nmcli("connection", "down", self.config.hotspot_connection_name, check=False)

    def configure_wifi(self, payload: dict[str, str]) -> ConfigureResult:
        validation_error = self.validate_configuration(payload)
        if validation_error:
            return ConfigureResult(success=False, message=validation_error)

        connection_name = self._connection_name_for(payload["ssid"])

        if self._connection_exists(connection_name):
            self._run_nmcli("connection", "delete", connection_name, check=False)

        try:
            shared_wifi_interface = self.config.hotspot_interface == self.config.client_wifi_interface
            if shared_wifi_interface:
                self.stop_hotspot()

            self._run_nmcli(
                "connection",
                "add",
                "type",
                "wifi",
                "ifname",
                self.config.client_wifi_interface,
                "con-name",
                connection_name,
                "ssid",
                payload["ssid"],
            )

            if payload.get("hidden") == "on":
                self._run_nmcli("connection", "modify", connection_name, "802-11-wireless.hidden", "yes")

            security_mode = payload["security_mode"]
            if security_mode == "open":
                pass
            elif security_mode == "psk":
                self._configure_psk(connection_name, payload)
            elif security_mode == "enterprise":
                self._configure_enterprise(connection_name, payload)

            self._run_nmcli(
                "connection",
                "up",
                connection_name,
                "ifname",
                self.config.client_wifi_interface,
                timeout=self.config.connection_wait_seconds,
            )

            connectivity = self.connectivity()
            if connectivity in {"connected", "connected (site only)", "full", "limited", "portal"}:
                self.stop_hotspot()
                return ConfigureResult(
                    success=True,
                    message="Connessione Wi-Fi configurata correttamente.",
                    connection_name=connection_name,
                    connectivity=connectivity,
                )

            self.stop_hotspot()
            return ConfigureResult(
                success=True,
                message="Connessione attivata, ma la connettivita' Internet e' limitata o richiede un portale.",
                connection_name=connection_name,
                connectivity=connectivity,
            )
        except NetworkManagerError as error:
            self._run_nmcli("connection", "delete", connection_name, check=False)
            self.ensure_hotspot()
            detail = error.stderr or error.stdout or "Errore sconosciuto di NetworkManager."
            return ConfigureResult(success=False, message=detail, connection_name=connection_name)

    def validate_configuration(self, payload: dict[str, str]) -> str | None:
        return self._validate_payload(payload)

    def _configure_psk(self, connection_name: str, payload: dict[str, str]) -> None:
        self._run_nmcli(
            "connection",
            "modify",
            connection_name,
            "wifi-sec.key-mgmt",
            "wpa-psk",
            "wifi-sec.psk",
            payload["password"],
        )

    def _configure_enterprise(self, connection_name: str, payload: dict[str, str]) -> None:
        eap_method = payload["enterprise_eap"].lower()
        phase2_auth = payload.get("phase2_auth", "mschapv2").lower()

        self._run_nmcli(
            "connection",
            "modify",
            connection_name,
            "wifi-sec.key-mgmt",
            "wpa-eap",
            "802-1x.eap",
            eap_method,
            "802-1x.identity",
            payload["identity"],
        )

        anonymous_identity = payload.get("anonymous_identity", "").strip()
        if anonymous_identity:
            self._run_nmcli("connection", "modify", connection_name, "802-1x.anonymous-identity", anonymous_identity)

        ca_cert = payload.get("ca_cert", "").strip()
        if ca_cert:
            self._run_nmcli("connection", "modify", connection_name, "802-1x.ca-cert", ca_cert)

        domain_suffix = payload.get("domain_suffix_match", "").strip()
        if domain_suffix:
            self._run_nmcli("connection", "modify", connection_name, "802-1x.domain-suffix-match", domain_suffix)

        if eap_method in {"peap", "ttls"}:
            self._run_nmcli(
                "connection",
                "modify",
                connection_name,
                "802-1x.password",
                payload["password"],
                "802-1x.phase2-auth",
                phase2_auth,
            )
        elif eap_method == "tls":
            self._run_nmcli(
                "connection",
                "modify",
                connection_name,
                "802-1x.client-cert",
                payload["client_cert"],
                "802-1x.private-key",
                payload["private_key"],
            )

            private_key_password = payload.get("private_key_password", "").strip()
            if private_key_password:
                self._run_nmcli(
                    "connection",
                    "modify",
                    connection_name,
                    "802-1x.private-key-password",
                    private_key_password,
                )
        else:
            raise NetworkManagerError(f"Metodo EAP non supportato: {eap_method}")

    def _validate_payload(self, payload: dict[str, str]) -> str | None:
        if not payload.get("ssid", "").strip():
            return "Inserisci l'SSID della rete."

        security_mode = payload.get("security_mode")
        if security_mode not in {"open", "psk", "enterprise"}:
            return "Modalita' di sicurezza non valida."

        if security_mode == "psk" and len(payload.get("password", "")) < 8:
            return "La password Wi-Fi deve contenere almeno 8 caratteri."

        if security_mode != "enterprise":
            return None

        eap_method = payload.get("enterprise_eap", "").lower()
        if eap_method not in {"peap", "ttls", "tls"}:
            return "Seleziona un metodo EAP supportato."

        if not payload.get("identity", "").strip():
            return "Per 802.1X serve l'identita' utente."

        if eap_method in {"peap", "ttls"} and not payload.get("password", ""):
            return "Per PEAP/TTLS serve la password enterprise."

        if eap_method == "tls":
            if not payload.get("client_cert", "").strip():
                return "Per EAP-TLS serve il percorso del certificato client."
            if not payload.get("private_key", "").strip():
                return "Per EAP-TLS serve il percorso della chiave privata."

        return None

    def _connection_exists(self, connection_name: str) -> bool:
        result = self._run_nmcli("-t", "-f", "NAME", "connection", "show", check=False)
        names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return connection_name in names

    def _connection_for_interface(self, interface: str) -> str:
        connection_name = self.active_connection_name_for_device(interface)
        if connection_name:
            return connection_name

        connection_name = f"setup-{interface}-ipv4"
        if self._connection_exists(connection_name):
            return connection_name

        device_type = self._device_type(interface)
        if device_type != "ethernet":
            raise NetworkManagerError("Per questa interfaccia serve prima una connessione attiva.")

        self._run_nmcli(
            "connection",
            "add",
            "type",
            "ethernet",
            "ifname",
            interface,
            "con-name",
            connection_name,
        )
        return connection_name

    def _connection_ipv4_method(self, connection_name: str | None) -> str | None:
        if not connection_name:
            return None
        result = self._run_nmcli("-t", "-g", "ipv4.method", "connection", "show", connection_name, check=False)
        value = result.stdout.strip()
        return value or None

    def _device_type(self, interface: str) -> str | None:
        result = self._run_nmcli("-t", "-f", "DEVICE,TYPE", "device", "status")
        for line in result.stdout.splitlines():
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            device, device_type = parts
            if device == interface:
                return device_type
        return None

    def _device_values(self, interface: str, field: str) -> list[str]:
        result = self._run_nmcli("-t", "-g", field, "device", "show", interface, check=False)
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _first_device_value(self, interface: str, field: str) -> str | None:
        values = self._device_values(interface, field)
        return values[0] if values else None

    def _split_dns(self, dns: str) -> list[str]:
        return [item for item in re.split(r"[\s,;]+", dns.strip()) if item]

    def _normalize_dns(self, dns: str) -> str:
        return ",".join(self._split_dns(dns))

    def _connection_name_for(self, ssid: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", ssid).strip("-")
        if not normalized:
            normalized = "wifi"
        return f"setup-{normalized[:40]}"
