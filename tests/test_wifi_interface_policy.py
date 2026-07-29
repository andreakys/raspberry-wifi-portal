from __future__ import annotations

import unittest
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import patch

from services.network_manager import NetworkManagerService


class WifiInterfacePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        config = SimpleNamespace(
            client_wifi_interface="wlan0",
            hotspot_interface="wlan0",
            connection_wait_seconds=45,
        )
        self.service = NetworkManagerService(config)  # type: ignore[arg-type]

    def test_usb_dongle_is_preferred_when_both_radios_exist(self) -> None:
        self.assertEqual(
            self.service.preferred_client_wifi_interface({"wlan0", "wlan1"}),
            "wlan1",
        )

    def test_integrated_radio_is_fallback_when_it_is_the_only_radio(self) -> None:
        self.assertEqual(
            self.service.preferred_client_wifi_interface({"wlan0"}),
            "wlan0",
        )

    def test_only_usb_radio_is_still_supported(self) -> None:
        self.assertEqual(
            self.service.preferred_client_wifi_interface({"wlan1"}),
            "wlan1",
        )

    def test_integrated_radio_is_not_selectable_with_two_radios(self) -> None:
        available = {"wlan0", "wlan1"}
        self.assertFalse(
            self.service.client_wifi_interface_is_selectable("wlan0", available)
        )
        self.assertTrue(
            self.service.client_wifi_interface_is_selectable("wlan1", available)
        )

    def test_client_configuration_on_wlan0_is_rejected_with_two_radios(self) -> None:
        payload = {
            "ssid": "Rete display",
            "wifi_interface": "wlan0",
            "security_mode": "open",
        }
        with patch.object(
            self.service,
            "_wifi_device_names",
            return_value={"wlan0", "wlan1"},
        ):
            error = self.service.validate_configuration(payload)

        self.assertIn("deve usare wlan1", error or "")

    def test_missing_selection_defaults_to_usb_dongle(self) -> None:
        self.assertEqual(
            self.service._target_wifi_interface(
                {}, available_names={"wlan0", "wlan1"}
            ),
            "wlan1",
        )

    def test_managed_wifi_profile_is_migrated_to_usb_dongle(self) -> None:
        connections = [
            {
                "name": "setup-rete-display",
                "type": "wifi",
                "device": "wlan0",
            },
            {
                "name": "setup-eth0-ipv4",
                "type": "ethernet",
                "device": "eth0",
            },
        ]
        with (
            patch.object(
                self.service,
                "_wifi_device_names",
                return_value={"wlan0", "wlan1"},
            ),
            patch.object(
                self.service,
                "list_managed_connections",
                return_value=connections,
            ),
            patch.object(
                self.service,
                "_connection_interface_name",
                return_value="wlan0",
            ),
            patch.object(self.service, "_run_nmcli") as run_nmcli,
        ):
            migrated = self.service.apply_client_interface_policy()

        self.assertEqual(migrated, ["setup-rete-display"])
        run_nmcli.assert_any_call(
            "connection",
            "modify",
            "setup-rete-display",
            "connection.interface-name",
            "wlan1",
        )
        run_nmcli.assert_any_call(
            "connection",
            "up",
            "setup-rete-display",
            "ifname",
            "wlan1",
            check=False,
            timeout=45,
        )

    def test_managed_wifi_profile_returns_to_integrated_radio_without_dongle(self) -> None:
        connections = [
            {
                "name": "setup-rete-display",
                "type": "wifi",
                "device": "",
            }
        ]
        with (
            patch.object(
                self.service,
                "_wifi_device_names",
                return_value={"wlan0"},
            ),
            patch.object(
                self.service,
                "list_managed_connections",
                return_value=connections,
            ),
            patch.object(
                self.service,
                "_connection_interface_name",
                return_value="wlan1",
            ),
            patch.object(self.service, "_run_nmcli") as run_nmcli,
        ):
            migrated = self.service.apply_client_interface_policy()

        self.assertEqual(migrated, ["setup-rete-display"])
        run_nmcli.assert_any_call(
            "connection",
            "modify",
            "setup-rete-display",
            "connection.interface-name",
            "wlan0",
        )

    def test_reconnect_tries_last_connection_first_and_uses_next_on_failure(self) -> None:
        connections = [
            {
                "name": "setup-altra-rete",
                "type": "wifi",
                "device": "",
            },
            {
                "name": "setup-ultima-rete",
                "type": "wifi",
                "device": "",
            },
        ]
        attempted: list[str] = []

        def run_nmcli(*args: str, **_kwargs: object) -> CompletedProcess[str]:
            if args[:2] == ("connection", "up"):
                attempted.append(args[2])
                return CompletedProcess(
                    ["nmcli", *args],
                    0 if args[2] == "setup-altra-rete" else 10,
                    "",
                    "",
                )
            return CompletedProcess(["nmcli", *args], 0, "", "")

        with (
            patch.object(
                self.service,
                "list_managed_connections",
                return_value=connections,
            ),
            patch.object(
                self.service,
                "_run_nmcli",
                side_effect=run_nmcli,
            ),
        ):
            connected = self.service.reconnect_managed_wifi(
                "wlan0",
                preferred_connection="setup-ultima-rete",
            )

        self.assertEqual(
            attempted,
            ["setup-ultima-rete", "setup-altra-rete"],
        )
        self.assertEqual(connected, "setup-altra-rete")

    def test_separate_client_radio_keeps_hotspot_during_stability_check(self) -> None:
        payload = {
            "ssid": "Rete display",
            "wifi_interface": "wlan1",
            "security_mode": "open",
        }
        with (
            patch.object(
                self.service,
                "_wifi_device_names",
                return_value={"wlan0", "wlan1"},
            ),
            patch.object(
                self.service,
                "_connection_exists",
                return_value=False,
            ),
            patch.object(
                self.service,
                "_run_nmcli",
                return_value=CompletedProcess(["nmcli"], 0, "", ""),
            ),
            patch.object(
                self.service,
                "connectivity",
                return_value="full",
            ),
            patch.object(self.service, "stop_hotspot") as stop_hotspot,
        ):
            result = self.service.configure_wifi(payload)

        self.assertTrue(result.success)
        stop_hotspot.assert_not_called()

    def test_shared_client_radio_stops_hotspot_before_connection(self) -> None:
        payload = {
            "ssid": "Rete display",
            "wifi_interface": "wlan0",
            "security_mode": "open",
        }
        with (
            patch.object(
                self.service,
                "_wifi_device_names",
                return_value={"wlan0"},
            ),
            patch.object(
                self.service,
                "_connection_exists",
                return_value=False,
            ),
            patch.object(
                self.service,
                "_run_nmcli",
                return_value=CompletedProcess(["nmcli"], 0, "", ""),
            ),
            patch.object(
                self.service,
                "connectivity",
                return_value="full",
            ),
            patch.object(self.service, "stop_hotspot") as stop_hotspot,
        ):
            result = self.service.configure_wifi(payload)

        self.assertTrue(result.success)
        stop_hotspot.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
