from __future__ import annotations

import unittest

from services.scan_policy import (
    can_pause_hotspot_without_losing_page,
    hotspot_blocks_scan,
)


class ScanPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.status = {
            "hotspot_active": True,
            "hotspot_interface": "wlan0",
            "client_wifi_interface": "wlan0",
            "active_client_interface": None,
            "lan_connected": False,
        }

    def test_only_selected_hotspot_radio_requires_pause(self) -> None:
        self.assertTrue(hotspot_blocks_scan(self.status, "wlan0"))
        self.assertFalse(hotspot_blocks_scan(self.status, "wlan1"))

    def test_default_radio_is_used_when_selection_is_missing(self) -> None:
        self.assertTrue(hotspot_blocks_scan(self.status))

    def test_hotspot_client_cannot_pause_without_losing_page(self) -> None:
        self.status["lan_connected"] = True
        self.assertFalse(
            can_pause_hotspot_without_losing_page(
                self.status, request_via_hotspot=True
            )
        )

    def test_lan_client_can_pause_hotspot_safely(self) -> None:
        self.status["lan_connected"] = True
        self.assertTrue(
            can_pause_hotspot_without_losing_page(
                self.status, request_via_hotspot=False
            )
        )

    def test_separate_active_wifi_is_an_alternate_path(self) -> None:
        self.status["active_client_interface"] = "wlan1"
        self.assertTrue(
            can_pause_hotspot_without_losing_page(
                self.status, request_via_hotspot=False
            )
        )


if __name__ == "__main__":
    unittest.main()
