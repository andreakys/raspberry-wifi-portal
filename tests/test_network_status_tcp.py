from __future__ import annotations

import socket
import unittest
from threading import Event, Thread

from services.network_status_tcp import (
    NetworkStatusTcpServer,
    build_network_status_line,
)


class NetworkStatusLineTests(unittest.TestCase):
    def test_wifi_off(self) -> None:
        line = build_network_status_line(
            {
                "internet_available": True,
                "wifi_enabled": False,
                "interfaces": [
                    {
                        "name": "eth0",
                        "type": "ethernet",
                        "ipv4_addresses": ["192.168.1.20/24"],
                        "ipv4_method": "auto",
                    }
                ],
            }
        )

        self.assertEqual(
            line,
            "internet: si, eth-ip: 192.168.1.20, eth-mode: DHCP, "
            "wi-fi enable: no, wi-fi off",
        )

    def test_hotspot_and_second_wifi_interface(self) -> None:
        line = build_network_status_line(
            {
                "internet_available": True,
                "wifi_enabled": True,
                "hotspot_active": True,
                "hotspot_interface": "wlan0",
                "hotspot_ssid": "Pi-Setup",
                "portal_address": "192.168.4.1",
                "interfaces": [
                    {
                        "name": "wlan1",
                        "type": "wifi",
                        "ssid": "Display-LAN",
                        "ipv4_addresses": ["10.0.0.41/24"],
                    },
                    {
                        "name": "wlan0",
                        "type": "wifi",
                        "ssid": "Pi-Setup",
                        "ipv4_addresses": ["192.168.4.1/24"],
                    },
                ],
            }
        )

        self.assertEqual(
            line,
            "internet: si, eth-ip: n/d, eth-mode: n/d, wi-fi enable: si, "
            "hot-spot: Pi-Setup / 192.168.4.1, "
            "wlan1: Display-LAN / 10.0.0.41",
        )

    def test_two_wifi_clients_are_sorted_and_values_have_no_commas(self) -> None:
        line = build_network_status_line(
            {
                "internet_available": False,
                "wifi_enabled": True,
                "hotspot_active": False,
                "interfaces": [
                    {
                        "name": "wlan1",
                        "type": "wifi",
                        "ssid": "Secondaria",
                        "ipv4_addresses": [],
                    },
                    {
                        "name": "eth0",
                        "type": "ethernet",
                        "ipv4_addresses": ["172.16.0.5/16"],
                        "ipv4_method": "manual",
                    },
                    {
                        "name": "wlan0",
                        "type": "wifi",
                        "ssid": "Rete, display",
                        "ipv4_addresses": ["192.168.50.8/24"],
                    },
                ],
            }
        )

        self.assertEqual(
            line,
            "internet: no, eth-ip: 172.16.0.5, eth-mode: static, "
            "wi-fi enable: si, wlan0: Rete display / 192.168.50.8, "
            "wlan1: Secondaria / n/d",
        )


class NetworkStatusTcpServerTests(unittest.TestCase):
    def test_sends_immediately_and_periodically(self) -> None:
        expected = "internet: si, eth-ip: 10.0.0.2, eth-mode: DHCP, wi-fi enable: no, wi-fi off"
        server = NetworkStatusTcpServer(
            lambda: expected,
            port=0,
            interval_seconds=0.1,
        )
        stop_event = Event()
        thread = Thread(target=server.serve_forever, args=(stop_event,), daemon=True)
        thread.start()
        self.assertTrue(server.ready.wait(2))
        self.assertIsNotNone(server.bound_port)

        with socket.create_connection(("127.0.0.1", int(server.bound_port)), timeout=2) as client:
            with client.makefile("r", encoding="utf-8") as stream:
                self.assertEqual(stream.readline().rstrip("\n"), expected)
                self.assertEqual(stream.readline().rstrip("\n"), expected)

        stop_event.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
