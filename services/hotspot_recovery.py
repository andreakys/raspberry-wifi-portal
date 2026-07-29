from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RecoveryAction = Literal[
    "none",
    "start-hotspot",
    "stop-hotspot",
    "retry-client",
]


@dataclass(frozen=True)
class RecoveryTimings:
    wifi_client_stable_seconds: int
    lan_stable_seconds: int
    no_access_hotspot_delay_seconds: int
    hotspot_client_retry_interval_seconds: int
    hotspot_minimum_up_seconds: int
    boot_connection_grace_seconds: int
    reconnect_grace_seconds: int
    disconnect_hotspot_threshold_seconds: int


@dataclass(frozen=True)
class RecoveryObservation:
    hotspot_active: bool
    wifi_client_healthy: bool
    lan_connected: bool
    has_separate_wifi_interfaces: bool
    managed_wifi_client_configured: bool
    network_recovering: bool
    hotspot_active_for: int
    wifi_client_stable_for: int
    lan_stable_for: int
    no_access_for: int
    seconds_since_client_retry: int | None
    last_access_kind: str | None
    manual_hold_remaining: int
    protected_reason: str | None = None


@dataclass(frozen=True)
class RecoveryDecision:
    action: RecoveryAction
    state: str
    reason: str
    message: str
    seconds_until_action: int | None = None


def _remaining(required: int, elapsed: int) -> int:
    return max(0, required - elapsed)


def decide_hotspot_recovery(
    observation: RecoveryObservation,
    timings: RecoveryTimings,
) -> RecoveryDecision:
    if observation.protected_reason:
        return RecoveryDecision(
            action="none",
            state="paused",
            reason=observation.protected_reason,
            message="Gestione automatica hotspot temporaneamente sospesa.",
        )

    if observation.hotspot_active:
        return _decide_while_hotspot_active(observation, timings)

    if observation.wifi_client_healthy:
        return RecoveryDecision(
            action="none",
            state="monitoring",
            reason="wifi-client-ok",
            message="Wi-Fi client disponibile: Pi-Setup non necessario.",
        )

    if observation.lan_connected:
        return RecoveryDecision(
            action="none",
            state="lan-standby",
            reason="lan-access",
            message="LAN disponibile: il portale resta raggiungibile senza Pi-Setup.",
        )

    return _decide_without_access(observation, timings)


def _decide_while_hotspot_active(
    observation: RecoveryObservation,
    timings: RecoveryTimings,
) -> RecoveryDecision:
    if observation.manual_hold_remaining > 0:
        return RecoveryDecision(
            action="none",
            state="manual-hotspot",
            reason="manual-hold",
            message="Pi-Setup mantenuto attivo manualmente.",
            seconds_until_action=observation.manual_hold_remaining,
        )

    minimum_up_remaining = _remaining(
        timings.hotspot_minimum_up_seconds,
        observation.hotspot_active_for,
    )

    if observation.wifi_client_healthy:
        stable_remaining = _remaining(
            timings.wifi_client_stable_seconds,
            observation.wifi_client_stable_for,
        )
        seconds_remaining = max(minimum_up_remaining, stable_remaining)
        if seconds_remaining == 0:
            return RecoveryDecision(
                action="stop-hotspot",
                state="stopping-hotspot",
                reason="wifi-client-stable",
                message="Wi-Fi client stabile: spegnimento automatico di Pi-Setup.",
            )
        return RecoveryDecision(
            action="none",
            state="wifi-stabilizing",
            reason="wifi-client-stabilizing",
            message="Wi-Fi client connessa: attendo la stabilita' prima di spegnere Pi-Setup.",
            seconds_until_action=seconds_remaining,
        )

    if observation.lan_connected:
        stable_remaining = _remaining(
            timings.lan_stable_seconds,
            observation.lan_stable_for,
        )
        seconds_remaining = max(minimum_up_remaining, stable_remaining)
        if seconds_remaining == 0:
            return RecoveryDecision(
                action="stop-hotspot",
                state="stopping-hotspot",
                reason="lan-stable",
                message="LAN stabile: spegnimento automatico di Pi-Setup.",
            )
        return RecoveryDecision(
            action="none",
            state="lan-stabilizing",
            reason="lan-stabilizing",
            message="LAN disponibile: attendo la stabilita' prima di spegnere Pi-Setup.",
            seconds_until_action=seconds_remaining,
        )

    if (
        not observation.has_separate_wifi_interfaces
        and observation.managed_wifi_client_configured
    ):
        retry_elapsed = (
            observation.seconds_since_client_retry
            if observation.seconds_since_client_retry is not None
            else observation.hotspot_active_for
        )
        retry_remaining = _remaining(
            timings.hotspot_client_retry_interval_seconds,
            retry_elapsed,
        )
        seconds_remaining = max(minimum_up_remaining, retry_remaining)
        if seconds_remaining == 0:
            return RecoveryDecision(
                action="retry-client",
                state="retrying-client",
                reason="single-radio-client-retry",
                message="Provo una rete Wi-Fi salvata usando la radio integrata.",
            )
        return RecoveryDecision(
            action="none",
            state="hotspot-active",
            reason="single-radio-retry-wait",
            message="Pi-Setup attivo; il prossimo tentativo Wi-Fi sara' automatico.",
            seconds_until_action=seconds_remaining,
        )

    return RecoveryDecision(
        action="none",
        state="hotspot-active",
        reason="no-alternate-access",
        message="Pi-Setup attivo: non e' disponibile un collegamento alternativo.",
    )


def _decide_without_access(
    observation: RecoveryObservation,
    timings: RecoveryTimings,
) -> RecoveryDecision:
    if observation.last_access_kind == "wifi":
        threshold = timings.disconnect_hotspot_threshold_seconds
        wait_reason = "wifi-client-loss"
        wait_message = "Wi-Fi client assente: attendo la soglia di recovery."
    elif observation.last_access_kind == "lan":
        threshold = timings.no_access_hotspot_delay_seconds
        wait_reason = "lan-loss"
        wait_message = "LAN non piu' disponibile: preparo Pi-Setup."
    else:
        threshold = timings.boot_connection_grace_seconds
        wait_reason = "boot-grace"
        wait_message = "Attendo la connessione iniziale prima di aprire Pi-Setup."

    if observation.network_recovering:
        threshold = max(threshold, timings.reconnect_grace_seconds)
        wait_reason = "reconnecting"
        wait_message = "La Wi-Fi client sta tentando di riconnettersi."

    seconds_remaining = _remaining(threshold, observation.no_access_for)
    if seconds_remaining == 0:
        return RecoveryDecision(
            action="start-hotspot",
            state="starting-hotspot",
            reason=wait_reason,
            message="Nessun accesso alternativo: attivazione automatica di Pi-Setup.",
        )

    return RecoveryDecision(
        action="none",
        state="waiting-hotspot",
        reason=wait_reason,
        message=wait_message,
        seconds_until_action=seconds_remaining,
    )
