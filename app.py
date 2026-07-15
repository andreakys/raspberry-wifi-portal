from __future__ import annotations

import ipaddress
import time
from hmac import compare_digest
from threading import Lock, Thread

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from config import load_config
from services.network_manager import (
    CONNECTED_DEVICE_STATES,
    CONNECTING_DEVICE_STATES,
    NetworkManagerError,
    NetworkManagerService,
)

config = load_config()
network_manager = NetworkManagerService(config)
app = Flask(__name__)
app.secret_key = config.portal_session_secret
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
provisioning_state = {
    "state": "idle",
    "message": "Nessuna configurazione in corso.",
    "connection_name": None,
    "connectivity": None,
    "interface": None,
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
scan_lock = Lock()
recovery_runtime = {
    "started_at": time.monotonic(),
    "suspend_until": 0.0,
    "disconnected_since": None,
    "last_client_seen_at": None,
}
wifi_scan_state = {
    "state": "idle",
    "message": "Nessuna scansione completa avviata.",
    "networks": [],
    "started_at": None,
    "completed_at": None,
    "last_error": None,
}


def _access_sheet(status: dict[str, object]) -> dict[str, str]:
    portal_url = f"http://{status['portal_address']}"

    return {
        "portal_url": portal_url,
        "hotspot_ssid": config.hotspot_ssid,
        "hotspot_password": config.hotspot_password,
        "portal_password": config.portal_password,
        "portal_title": config.portal_title,
    }


def _hotspot_blocks_client_scan(status: dict[str, object]) -> bool:
    return (
        bool(status.get("hotspot_active"))
        and status.get("hotspot_interface") == status.get("client_wifi_interface")
    )


def _request_from_hotspot_network() -> bool:
    remote_addr = request.remote_addr or ""
    try:
        client_address = ipaddress.ip_address(remote_addr)
        hotspot_network = ipaddress.ip_network(config.hotspot_address, strict=False)
    except ValueError:
        return False
    return client_address in hotspot_network


def _can_scan_without_losing_page(status: dict[str, object]) -> bool:
    return bool(status.get("lan_connected")) and not _request_from_hotspot_network()


def _networks_are_only_hotspot(networks: list[dict[str, str]]) -> bool:
    visible_ssids = {network.get("ssid", "") for network in networks if network.get("ssid")}
    return not visible_ssids or visible_ssids == {config.hotspot_ssid}


def _scan_state_snapshot() -> dict[str, object]:
    with scan_lock:
        return {
            **wifi_scan_state,
            "networks": list(wifi_scan_state["networks"]),
        }


def _set_scan_state(**updates: object) -> None:
    with scan_lock:
        wifi_scan_state.update(updates)


def _choose_visible_networks(live_networks: list[dict[str, str]], scan_limited: bool) -> list[dict[str, str]]:
    scan_state = _scan_state_snapshot()
    cached_networks = scan_state.get("networks", [])
    if (
        scan_limited
        and scan_state.get("state") == "completed"
        and isinstance(cached_networks, list)
        and cached_networks
        and _networks_are_only_hotspot(live_networks)
    ):
        return cached_networks
    return live_networks


def _run_full_wifi_scan_cycle() -> None:
    _set_scan_state(
        state="running",
        message=(
            "Scansione completa in corso: l'hotspot viene spento per pochi secondi "
            "e verra' riattivato automaticamente."
        ),
        started_at=int(time.time()),
        completed_at=None,
        last_error=None,
    )
    _pause_hotspot_recovery(config.hotspot_cooldown_seconds, "manual-full-scan")

    try:
        visible_networks = _scan_networks_with_hotspot_paused()
        _set_scan_state(
            state="completed",
            message=(
                f"Scansione completa terminata: {len(visible_networks)} reti trovate. "
                "Ricollegati all'hotspot e aggiorna questa pagina."
            ),
            networks=visible_networks,
            completed_at=int(time.time()),
            last_error=None,
        )
    except NetworkManagerError as error:
        detail = error.stderr or error.stdout or str(error)
        try:
            network_manager.ensure_hotspot()
        except NetworkManagerError:
            pass
        _set_scan_state(
            state="error",
            message="Scansione completa non riuscita; hotspot riattivato se possibile.",
            completed_at=int(time.time()),
            last_error=detail,
        )


def _scan_networks_with_hotspot_paused(wifi_interface: str | None = None) -> list[dict[str, str]]:
    hotspot_was_active = network_manager.hotspot_active()
    try:
        time.sleep(2)
        if hotspot_was_active:
            network_manager.stop_hotspot()
            time.sleep(3)
        network_manager.ensure_wifi_enabled()
        networks = network_manager.list_networks(wifi_interface)
        visible_networks = [
            network for network in networks if network.get("ssid") != config.hotspot_ssid
        ]
        if hotspot_was_active:
            network_manager.ensure_hotspot()
        return visible_networks
    except NetworkManagerError:
        if hotspot_was_active:
            try:
                network_manager.ensure_hotspot()
            except NetworkManagerError:
                pass
        raise


def _is_authenticated() -> bool:
    return bool(session.get("authenticated"))


def _safe_next(default: str = "/") -> str:
    target = request.values.get("next", default)
    if not target.startswith("/") or target.startswith("//"):
        return default
    return target


@app.before_request
def require_portal_login():
    if request.endpoint in {"login", "login_submit", "static"}:
        return None

    if _is_authenticated():
        return None

    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "login-required"}), 401

    return redirect(url_for("login", next=request.full_path if request.query_string else request.path))


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
        live_networks = network_manager.list_networks()
    except NetworkManagerError:
        live_networks = []
    scan_limited = _hotspot_blocks_client_scan(status)
    lan_safe_scan = scan_limited and _can_scan_without_losing_page(status)
    networks = _choose_visible_networks(live_networks, scan_limited)
    return (
        render_template(
            "index.html",
            page_title=config.portal_title,
            app_version=config.app_version,
            hotspot_ssid=config.hotspot_ssid,
            portal_address=status["portal_address"],
            status=status,
            networks=networks,
            scan_limited=scan_limited,
            lan_safe_scan=lan_safe_scan,
            full_scan=_scan_state_snapshot(),
            access_sheet=_access_sheet(status),
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
    provisioning_state["interface"] = result.interface
    _pause_hotspot_recovery(config.hotspot_cooldown_seconds, "post-provisioning")


def _wifi_client_is_healthy(status: dict[str, object]) -> bool:
    device_state = str(status.get("device_state", "")).lower()
    active_client_connection = status.get("active_client_connection")
    return bool(active_client_connection) and device_state in CONNECTED_DEVICE_STATES


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

        if _wifi_client_is_healthy(status):
            recovery_runtime["last_client_seen_at"] = now
            recovery_runtime["disconnected_since"] = None
            _set_recovery_state(
                state="monitoring",
                reason="wifi-client-ok",
                message="Wi-Fi client disponibile, hotspot temporaneo non necessario.",
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
        lan_connected = bool(status.get("lan_connected"))

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
                message="La Wi-Fi client sta tentando il recupero della rete configurata.",
                seconds_without_network=disconnected_for,
            )
        elif recovery_runtime["last_client_seen_at"] is None and not active_client_connection:
            threshold = config.boot_connection_grace_seconds
            message = "Attendo il tempo di grace al boot prima di riaprire l'hotspot per configurare la Wi-Fi."
            if lan_connected:
                message = (
                    "LAN cablata presente, ma Wi-Fi client non connessa: "
                    "attendo il grace al boot prima di aprire l'hotspot di setup."
                )
            _set_recovery_state(
                state="boot-wait",
                reason="boot-grace",
                message=message,
                seconds_without_network=since_boot,
            )
        else:
            threshold = config.disconnect_hotspot_threshold_seconds
            message = "Wi-Fi client assente, ma ancora entro la soglia di tolleranza."
            if lan_connected:
                message = (
                    "LAN cablata presente, ma Wi-Fi client assente: "
                    "attendo la soglia prima di riaprire l'hotspot."
                )
            _set_recovery_state(
                state="waiting-loss-threshold",
                reason="wifi-client-loss",
                message=message,
                seconds_without_network=disconnected_for,
            )

        if disconnected_for >= threshold or since_boot >= threshold and threshold == config.boot_connection_grace_seconds:
            try:
                network_manager.ensure_hotspot()
                recovery_runtime["disconnected_since"] = None
                recovery_runtime["suspend_until"] = now + config.hotspot_cooldown_seconds
                reactivation_reason = (
                    "wifi-client-not-configured"
                    if recovery_runtime["last_client_seen_at"] is None
                    else "wifi-client-loss"
                )
                _set_recovery_state(
                    state="hotspot-reactivated",
                    reason=reactivation_reason,
                    message="Hotspot temporaneo riattivato automaticamente per configurare o recuperare la Wi-Fi client.",
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


@app.get("/login")
def login():
    if _is_authenticated():
        return redirect(_safe_next())

    return render_template(
        "login.html",
        page_title=config.portal_title,
        app_version=config.app_version,
        hotspot_ssid=config.hotspot_ssid,
        error_message=None,
        next_url=_safe_next(),
    )


@app.post("/login")
def login_submit():
    submitted_password = request.form.get("portal_password", "")
    if compare_digest(submitted_password, config.portal_password):
        session.clear()
        session["authenticated"] = True
        return redirect(_safe_next())

    return (
        render_template(
            "login.html",
            page_title=config.portal_title,
            app_version=config.app_version,
            hotspot_ssid=config.hotspot_ssid,
            error_message="Password portale non valida.",
            next_url=_safe_next(),
        ),
        401,
    )


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.post("/system/reboot")
def reboot_system():
    try:
        network_manager.reboot_system()
    except NetworkManagerError as error:
        return _render_index(network_error=str(error), status_code=500)

    return render_template(
        "status.html",
        page_title=config.portal_title,
        app_version=config.app_version,
        success=True,
        pending=False,
        status_eyebrow="Sistema",
        status_title="Riavvio in corso",
        message="Il dispositivo sta eseguendo il riavvio. Attendi circa un minuto prima di ricollegarti al portale.",
        connection_name="Sistema",
        connectivity="reboot",
        interface=None,
        interface_label=None,
    )


@app.get("/")
def index():
    return _render_index()


@app.get("/access-sheet")
def access_sheet():
    status = network_manager.current_status()
    return render_template(
        "access_sheet.html",
        page_title=config.portal_title,
        app_version=config.app_version,
        status=status,
        access_sheet=_access_sheet(status),
    )


@app.get("/quick-guide")
def quick_guide():
    status = network_manager.current_status()
    return render_template(
        "quick_guide.html",
        page_title=config.portal_title,
        app_version=config.app_version,
        status=status,
        access_sheet=_access_sheet(status),
    )


@app.get("/api/status")
def api_status():
    return jsonify(
        {
            "network": network_manager.current_status(),
            "app": {
                "title": config.portal_title,
                "version": config.app_version,
            },
            "provisioning": provisioning_state,
            "recovery": recovery_state,
            "full_scan": _scan_state_snapshot(),
        }
    )


@app.get("/api/networks")
def api_networks():
    status = network_manager.current_status()
    wifi_interface = request.args.get("wifi_interface", "").strip() or config.client_wifi_interface
    scan_limited = bool(status.get("hotspot_active")) and status.get("hotspot_interface") == wifi_interface
    if scan_limited and _can_scan_without_losing_page(status):
        try:
            _pause_hotspot_recovery(config.hotspot_cooldown_seconds, "lan-full-scan")
            networks = _scan_networks_with_hotspot_paused(wifi_interface)
            _set_scan_state(
                state="completed",
                message=(
                    f"Scansione via LAN terminata: {len(networks)} reti trovate. "
                    "La pagina e' rimasta raggiungibile tramite la LAN cablata."
                ),
                networks=networks,
                started_at=int(time.time()),
                completed_at=int(time.time()),
                last_error=None,
            )
            return jsonify(
                {
                    "networks": networks,
                    "mode": "lan-full-scan",
                    "message": "Scansione completa eseguita tramite LAN cablata.",
                }
            )
        except NetworkManagerError as error:
            detail = error.stderr or error.stdout or str(error)
            _set_scan_state(
                state="error",
                message="Scansione via LAN non riuscita; hotspot riattivato se possibile.",
                completed_at=int(time.time()),
                last_error=detail,
            )
            return jsonify({"networks": [], "mode": "error", "message": detail}), 500

    try:
        networks = network_manager.list_networks(wifi_interface)
    except NetworkManagerError:
        networks = []
    return jsonify({"networks": networks, "mode": "live-scan"})


@app.get("/api/networks/full-scan")
def api_full_scan_state():
    return jsonify(_scan_state_snapshot())


@app.post("/api/networks/full-scan")
def api_start_full_scan():
    status = network_manager.current_status()
    if not _hotspot_blocks_client_scan(status):
        return jsonify(
            {
                "ok": False,
                "error": "full-scan-not-needed",
                "message": "La scansione completa serve solo quando hotspot e Wi-Fi client usano la stessa interfaccia.",
            }
        ), 400

    current_scan = _scan_state_snapshot()
    if current_scan.get("state") == "running":
        return jsonify({"ok": True, "scan": current_scan})

    worker = Thread(target=_run_full_wifi_scan_cycle, daemon=True)
    worker.start()
    return jsonify(
        {
            "ok": True,
            "scan": _scan_state_snapshot(),
            "message": "Scansione completa avviata. Il telefono perdera' Pi-Setup per alcuni secondi.",
        }
    )


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
    provisioning_state["message"] = "Il dispositivo sta disattivando l'hotspot temporaneo e sta provando la nuova rete."
    provisioning_state["connection_name"] = None
    provisioning_state["connectivity"] = None
    provisioning_state["interface"] = payload.get("wifi_interface")

    worker = Thread(target=_apply_configuration, args=(payload.copy(),), daemon=True)
    worker.start()

    return render_template(
        "status.html",
        page_title=config.portal_title,
        app_version=config.app_version,
        success=True,
        pending=True,
        message=provisioning_state["message"],
        connection_name=None,
        connectivity=None,
        interface=payload.get("wifi_interface"),
        interface_label=network_manager.interface_display_name(payload.get("wifi_interface", "")),
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


@app.post("/network/connections/delete")
def delete_network_connection():
    connection_name = request.form.get("connection_name", "").strip()
    try:
        network_manager.delete_managed_connection(connection_name)
    except NetworkManagerError as error:
        detail = error.stderr or error.stdout or str(error)
        return _render_index(network_error=detail, status_code=400)

    return _render_index(network_message=f"Connessione eliminata: {connection_name}.")


if __name__ == "__main__":
    _bootstrap_network_manager()
    _start_background_threads()
    app.run(host=config.host, port=config.port, debug=config.debug)
