from __future__ import annotations

import unittest

from services.user_documents import (
    LOGO_PATH,
    build_access_sheet_pdf,
    build_portal_qr_svg,
    build_quick_guide_pdf,
)


class UserDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.access_data = {
            "portal_url": "http://192.168.4.1",
            "hotspot_ssid": "Pi-Setup",
            "hotspot_password": "HotspotTest123!",
            "portal_password": "PortalTest456!",
            "portal_title": "VT Network Manager",
            "company": {
                "name": "Visualtronics s.a.s.",
                "address": "Via Galimberti, 75/2 - 10040 Piobesi Torinese",
                "registration": "C.F./P.I. 02638430047",
                "email": "info@visualtronics.com",
            },
            "network_interfaces": [
                {
                    "name": "eth0",
                    "display_name": "eth0",
                    "type": "ethernet",
                    "mac_address": "DC:A6:32:01:02:03",
                },
                {
                    "name": "wlan0",
                    "display_name": "wlan0 - Wi-Fi integrata",
                    "type": "wifi",
                    "mac_address": "B8:27:EB:04:05:06",
                },
            ],
        }

    def test_portal_qr_is_svg(self) -> None:
        svg = build_portal_qr_svg(self.access_data["portal_url"])

        self.assertIn(b"<svg", svg)
        self.assertIn(b"</svg>", svg)
        self.assertGreater(len(svg), 1_000)

    def test_visualtronics_logo_is_packaged(self) -> None:
        self.assertTrue(LOGO_PATH.is_file())
        self.assertGreater(LOGO_PATH.stat().st_size, 10_000)

    def test_access_sheet_is_a_pdf_with_clickable_portal_link(self) -> None:
        pdf = build_access_sheet_pdf(
            "VT Network Manager",
            "1.19.0",
            self.access_data,
        )

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 4_000)
        self.assertGreaterEqual(pdf.count(b"http://192.168.4.1"), 2)
        self.assertIn(b"/URI", pdf)

    def test_quick_guide_is_a_pdf_with_clickable_portal_link(self) -> None:
        pdf = build_quick_guide_pdf(
            "VT Network Manager",
            "1.19.0",
            self.access_data,
        )

        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf), 7_000)
        self.assertIn(b"http://192.168.4.1", pdf)
        self.assertIn(b"/URI", pdf)

    def test_special_characters_in_credentials_do_not_break_pdf(self) -> None:
        data = {
            **self.access_data,
            "hotspot_ssid": "Display <Nord>",
            "hotspot_password": "A&B<123>",
            "portal_password": "C&D<456>",
        }

        pdf = build_access_sheet_pdf("VT Network Manager", "1.19.0", data)

        self.assertTrue(pdf.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
