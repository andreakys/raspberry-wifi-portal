from __future__ import annotations

import time
from threading import Lock, Thread

from flask import Flask, jsonify, render_template, request

from config import load_config
from services.network_manager import (
    CONNECTED_CONNECTIVITY_STATES,
    CONNECTED_DEVICE_STATES,
    CONNECTING_DEVICE_STATES,
    NetworkManagerError,
    NetworkManagerService,
)

config = load_config()
network_manager = NetworkManagerService(config)
app = Flask(__name__)
provisioning_state = {
    "state": "idle",
    "message": "Nessuna configurazione in corso.",
    "connection_name": None,
    "connectivity": None,
}
recovery_state = {
    "state": "starting",
    "message": "Monitoraggio rete in avvio.",
    "reason": None,
    "seconds_without_network": 0,
    "hotspot_reactivation_count": 0,
    "last_transition_at": None,
    "last_error": None,
}
recovery_lock = Lock()
recovery_runtime = {
    "started_at": time.monotonic(),
    "suspend_until": 0.0,
    "disconnected_since": None,
    "last_client_seen_at": None,
}


def _set_recovery_state(**updates: object) -> None:
    with recovery_lock:
        recovery_state.update(updates)
        recovery_state["last_transition_at"] = int(time.time())


def _pause_hotspot_recovery(seconds: int, reason: str) -> None:
    recovery_runtime["suspend_until"] = max(recovery_runtime["suspend_until"], time.monotonic() + seconds)
    _set_recovery_state(
        state="cooldown",
        reason=reason,
        message=f"Recovery hotspot sospeso per {seconds} secondi.",
    )


def _bootstrap_network_manager() -> None:
    try:
        network_manager.ensure_wifi_enabled()
    except NetworkManagerError:
        _set_recovery_state(
            state="warning",
            reason="wifi-enable-failed",
            message="Impossibile attivare subito il Wi-Fi; il monitor continuera' a riprovare.",
        )


def _render_index(
    error_message: str | None = None,
    network_message: str | None = None,
    network_error: str | None = None,
    status_code: int = 200,
):
    status = network_manager.current_status()
    try:
        networks = network_manager.list_networks()
    except NetworkManagerError:
        networks = []
    return (
        render_template(
            "index.html",
            page_title=config.portal_title,
            hotspot_ssid=config.hotspot_ssid,
            portal_address=status["portal_address"],
            status=status,
            networks=networks,
            error_message=error_message,
            network_message=network_message,
            network_error=network_error,
        ),
        status_code,
    )


def _apply_configuration(payload: dict[str, str]) -> None:
    result = network_manager.configure_wifi(payload)
    provisioning_state["state"] = "success" if result.success else "error"
    provisioning_state["message"] = result.message
    provisioning_state["connection_name"] = result.connection_name
    provisioning_state["connectivity"] = result.connectivity
    _pause_hotspot_recovery(config.hotspot_cooldown_seconds, "post-provisioning")


def _network_is_healthy(status: dict[str, object]) -> bool:
    connectivity = str(status.get("connectivity", "")).lower()
    device_state = str(status.get("device_state", "")).lower()
    return connectivity in CONNECTED_CONNECTIVITY_STATES or device_state in CONNECTED_DEVICE_STATES


def _network_is_recovering(status: dict[str, object]) -> bool:
    device_state = str(status.get("device_state", "")).lower()
    return device_state in CONNECTING_DEVICE_STATES


def _run_recovery_monitor() -> None:
    while True:
        now = time.monotonic()

        if provisioning_state["state"] == "running":
            recovery_runtime["disconnected_since"] = None
            _set_recovery_state(
                state="paused",
                reason="provisioning",
                message="Configurazione Wi-Fi in corso, recovery hotspot in pausa.",
                seconds_without_network=0,
            )
            time.sleep(config.recovery_check_interval_seconds)
            continue

        try:
            status = network_manager.current_status()
            recovery_state["last_error"] = None
        except NetworkManagerError as error:
            detail = error.stderr or error.stdout or str(error)
            _set_recovery_state(
                state="warning",
                reason="status-error",
                message="Errore nel controllo dello stato rete; nuovo tentativo al prossimo ciclo.",
                last_error=detail,
            )
            time.sleep(config.recovery_check_interval_seconds)
            continue

        if status["hotspot_active"]:
            recovery_runtime["disconnected_since"] = None
            _set_recovery_state(
                state="hotspot-active",
                reason="hotspot-active",
                message="Hotspot temporaneo attivo.",
                seconds_without_network=0,
            )
            time.sleep(config.recovery_check_interval_seconds)
            continue

        if _network_is_healthy(status):
            recovery_runtime["last_client_seen_at"] = now
            recovery_runtime["disconnected_since"] = None
            _set_recovery_state(
                state="monitoring",
                reason="network-ok",
                message="Rete disponibile, hotspot temporaneo non necessario.",
                seconds_without_network=0,
            )
            time.sleep(config.recovery_check_interval_seconds)
            continue

        if recovery_runtime["disconnected_since"] is None:
            recovery_runtime["disconnected_since"] = now

        disconnected_for = int(now - float(recovery_runtime["disconnected_since"]))
        since_boot = int(now - float(recovery_runtime["started_at"]))
        suspend_until = float(recovery_runtime["suspend_until"])
        active_client_connection = status.get("active_client_connection")

        if now < suspend_until:
            _set_recovery_state(
                state="cooldown",
                reason="cooldown",
                message="Recovery hotspot in attesa per evitare falsi positivi su disconnessioni temporanee.",
                seconds_without_network=disconnected_for,
            )
            time.sleep(config.recovery_check_interval_seconds)
            continue

        if _network_is_recovering(status):
            threshold = max(config.reconnect_grace_seconds, config.disconnect_hotspot_threshold_seconds)
            _set_recovery_state(
                state="reconnecting",
                reason="reconnecting",
                message="Il Raspberry sta tentando il recupero della rete Wi-Fi aziendale.",
                seconds_without_network=disconnected_for,
            )
        elif recovery_runtime["last_client_seen_at"] is None and not active_client_connection:
            threshold = config.boot_connection_grace_seconds
            _set_recovery_state(
                state="boot-wait",
                reason="boot-grace",
                message="Attendo il tempo di grace al boot prima di riaprire l'hotspot.",
                seconds_without_network=since_boot,
            )
        else:
            threshold = config.disconnect_hotspot_threshold_seconds
            _set_recovery_state(
                state="waiting-loss-threshold",
                reason="temporary-loss",
                message="Rete assente, ma ancora entro la soglia di tolleranza per disconnessioni temporanee.",
                seconds_without_network=disconnected_for,
            )

        if disconnected_for >= threshold or since_boot >= threshold and threshold == config.boot_connection_grace_seconds:
            try:
                network_manager.ensure_hotspot()
                recovery_runtime["disconnected_since"] = None
                recovery_runtime["suspend_until"] = now + config.hotspot_cooldown_seconds
                _set_recovery_state(
                    state="hotspot-reactivated",
                    reason="boot-failed" if recovery_runtime["last_client_seen_at"] is None else "network-loss",
                    message="Hotspot temporaneo riattivato automaticamente dopo perdita prolungata della rete.",
                    seconds_without_network=0,
                    hotspot_reactivation_count=int(recovery_state["hotspot_reactivation_count"]) + 1,
                )
            except NetworkManagerError as error:
                detail = error.stderr or error.stdout or str(error)
                _set_recovery_state(
                    state="warning",
                    reason="hotspot-start-failed",
                    message="Tentativo di riattivazione hotspot fallito; nuovo tentativo al prossimo ciclo.",
                    last_error=detail,
                    seconds_without_network=disconnected_for,
                )

        time.sleep(config.recovery_check_interval_seconds)


def _start_background_threads() -> None:
    if config.auto_recovery_enabled:
        monitor = Thread(target=_run_recovery_monitor, daemon=True)
        monitor.start()


@app.get("/")
def index():
    return _render_index()


@app.get("/api/status")
def api_status():
    return jsonify(
        {
            "network": network_manager.current_status(),
            "provisioning": provisioning_state,
            "recovery": recovery_state,
        }
    )


@app.get("/api/networks")
def api_networks():
    try:
        networks = network_manager.list_networks()
    except NetworkManagerError:
        networks = []
    return jsonify({"networks": networks})


@app.post("/configure")
def configure():
    payload = {key: value.strip() for key, value in request.form.items()}
    if "hidden" in request.form:
        payload["hidden"] = request.form["hidden"]
    payload["password"] = payload.get("psk_password") or payload.get("enterprise_password") or ""

    validation_error = network_manager.validate_configuration(payload)
    if validation_error:
        return _render_index(error_message=validation_error, status_code=400)

    provisioning_state["state"] = "running"
    provisioning_state["message"] = "Il Raspberry sta disattivando l'hotspot temporaneo e sta provando la nuova rete."
    provisioning_state["connection_name"] = None
    provisioning_state["connectivity"] = None

    worker = Thread(target=_apply_configuration, args=(payload.copy(),), daemon=True)
    worker.start()

    return render_template(
        "status.html",
        page_title=config.portal_title,
        success=True,
        pending=True,
        message=provisioning_state["message"],
        connection_name=None,
        connectivity=None,
    )


@app.get("/api/provisioning")
def api_provisioning():
    return jsonify(provisioning_state)


@app.get("/api/recovery")
def api_recovery():
    return jsonify(recovery_state)


@app.post("/hotspot/restart")
def restart_hotspot():
    network_manager.ensure_hotspot()
    _pause_hotspot_recovery(config.hotspot_cooldown_seconds, "manual-hotspot")
    return jsonify({"ok": True, "status": network_manager.current_status()})


@app.post("/network/ipv4")
def configure_network_ipv4():
    payload = {key: value.strip() for key, value in request.form.items()}
    try:
        connection_name = network_manager.configure_interface_ipv4(payload)
    except NetworkManagerError as error:
        detail = error.stderr or error.stdout or str(error)
        return _render_index(network_error=detail, status_code=400)

    mode = payload.get("ip_mode", "").lower()
    if mode == "dhcp":
        message = f"DHCP applicato a {payload.get('interface')} ({connection_name})."
    else:
        message = f"Indirizzo statico applicato a {payload.get('interface')} ({connection_name})."

    return _render_index(network_message=message)


if __name__ == "__main__":
    _bootstrap_network_manager()
    _start_background_threads()
    app.run(host=config.host, port=config.port, debug=config.debug)
