from __future__ import annotations

import unittest
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import patch

from services.network_manager import NetworkManagerService


class NetworkInterfaceStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        config = SimpleNamespace(
            hotspot_interface="wlan0",
            hotspot_connection_name="Pi Setup AP",
            hotspot_ssid="Pi-Setup",
        )
        self.service = NetworkManagerService(config)  # type: ignore[arg-type]

    def test_interface_status_contains_normalized_mac_addresses(self) -> None:
        device_status = CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "eth0:ethernet:connected:netplan-eth0\n"
                "wlan0:wifi:disconnected:--\n"
            ),
            stderr="",
        )

        def first_value(interface: str, field: str) -> str | None:
            values = {
                ("eth0", "IP4.GATEWAY"): "192.168.1.1",
                ("eth0", "GENERAL.HWADDR"): "dc\\:a6\\:32\\:01\\:02\\:03",
                ("wlan0", "IP4.GATEWAY"): None,
                ("wlan0", "GENERAL.HWADDR"): "B8:27:EB:04:05:06",
            }
            return values.get((interface, field))

        with (
            patch.object(self.service, "_run_nmcli", return_value=device_status),
            patch.object(self.service, "hotspot_active", return_value=False),
            patch.object(self.service, "_device_values", return_value=[]),
            patch.object(
                self.service,
                "_first_device_value",
                side_effect=first_value,
            ),
            patch.object(
                self.service,
                "_connection_ipv4_method",
                return_value="auto",
            ),
        ):
            interfaces = self.service.list_ip_interfaces()

        self.assertEqual(interfaces[0]["mac_address"], "DC:A6:32:01:02:03")
        self.assertEqual(interfaces[1]["mac_address"], "B8:27:EB:04:05:06")

    def test_invalid_mac_address_is_not_exposed(self) -> None:
        with patch.object(
            self.service,
            "_first_device_value",
            return_value="not-a-mac",
        ):
            self.assertIsNone(self.service._device_mac_address("eth0"))


if __name__ == "__main__":
    unittest.main()
