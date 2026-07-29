from __future__ import annotations

import unittest

from services.hotspot_recovery import (
    RecoveryObservation,
    RecoveryTimings,
    decide_hotspot_recovery,
)


class HotspotRecoveryPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timings = RecoveryTimings(
            wifi_client_stable_seconds=30,
            lan_stable_seconds=120,
            no_access_hotspot_delay_seconds=20,
            hotspot_client_retry_interval_seconds=300,
            hotspot_minimum_up_seconds=30,
            boot_connection_grace_seconds=75,
            reconnect_grace_seconds=45,
            disconnect_hotspot_threshold_seconds=180,
        )

    def observation(self, **updates: object) -> RecoveryObservation:
        values: dict[str, object] = {
            "hotspot_active": True,
            "wifi_client_healthy": False,
            "lan_connected": False,
            "has_separate_wifi_interfaces": False,
            "managed_wifi_client_configured": False,
            "network_recovering": False,
            "hotspot_active_for": 300,
            "wifi_client_stable_for": 0,
            "lan_stable_for": 0,
            "no_access_for": 0,
            "seconds_since_client_retry": None,
            "last_access_kind": None,
            "manual_hold_remaining": 0,
            "protected_reason": None,
        }
        values.update(updates)
        return RecoveryObservation(**values)  # type: ignore[arg-type]

    def test_dual_radio_stops_hotspot_after_stable_wifi(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                wifi_client_healthy=True,
                has_separate_wifi_interfaces=True,
                wifi_client_stable_for=30,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "stop-hotspot")
        self.assertEqual(decision.reason, "wifi-client-stable")

    def test_dual_radio_waits_for_wifi_stability(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                wifi_client_healthy=True,
                has_separate_wifi_interfaces=True,
                wifi_client_stable_for=12,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "none")
        self.assertEqual(decision.seconds_until_action, 18)

    def test_stable_lan_stops_hotspot(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                lan_connected=True,
                lan_stable_for=120,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "stop-hotspot")
        self.assertEqual(decision.reason, "lan-stable")

    def test_unstable_lan_keeps_hotspot_available(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                lan_connected=True,
                lan_stable_for=45,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "none")
        self.assertEqual(decision.seconds_until_action, 75)

    def test_single_radio_retries_saved_client_after_interval(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                managed_wifi_client_configured=True,
                seconds_since_client_retry=300,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "retry-client")

    def test_single_radio_without_managed_profile_keeps_hotspot(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(managed_wifi_client_configured=False),
            self.timings,
        )
        self.assertEqual(decision.action, "none")
        self.assertEqual(decision.reason, "no-alternate-access")

    def test_boot_without_access_starts_hotspot_after_grace(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                hotspot_active=False,
                hotspot_active_for=0,
                no_access_for=75,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "start-hotspot")

    def test_lan_loss_starts_hotspot_quickly(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                hotspot_active=False,
                hotspot_active_for=0,
                no_access_for=20,
                last_access_kind="lan",
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "start-hotspot")
        self.assertEqual(decision.reason, "lan-loss")

    def test_wifi_loss_keeps_original_longer_threshold(self) -> None:
        waiting = decide_hotspot_recovery(
            self.observation(
                hotspot_active=False,
                hotspot_active_for=0,
                no_access_for=60,
                last_access_kind="wifi",
            ),
            self.timings,
        )
        ready = decide_hotspot_recovery(
            self.observation(
                hotspot_active=False,
                hotspot_active_for=0,
                no_access_for=180,
                last_access_kind="wifi",
            ),
            self.timings,
        )
        self.assertEqual(waiting.action, "none")
        self.assertEqual(waiting.seconds_until_action, 120)
        self.assertEqual(ready.action, "start-hotspot")

    def test_manual_hold_prevents_automatic_stop(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                wifi_client_healthy=True,
                has_separate_wifi_interfaces=True,
                wifi_client_stable_for=120,
                manual_hold_remaining=240,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "none")
        self.assertEqual(decision.reason, "manual-hold")

    def test_protected_operation_prevents_state_change(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                wifi_client_healthy=True,
                has_separate_wifi_interfaces=True,
                wifi_client_stable_for=120,
                protected_reason="wifi-scan",
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "none")
        self.assertEqual(decision.reason, "wifi-scan")

    def test_lan_keeps_inactive_hotspot_in_standby(self) -> None:
        decision = decide_hotspot_recovery(
            self.observation(
                hotspot_active=False,
                hotspot_active_for=0,
                lan_connected=True,
                lan_stable_for=10,
            ),
            self.timings,
        )
        self.assertEqual(decision.action, "none")
        self.assertEqual(decision.reason, "lan-access")


if __name__ == "__main__":
    unittest.main()
