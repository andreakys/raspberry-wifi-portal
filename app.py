from __future__ import annotations

import ipaddress
import time
from hmac import compare_digest
from threading import Lock, RLock, Thread

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from config import load_config
from services.hotspot_recovery import (
    RecoveryDecision,
    RecoveryObservation,
    RecoveryTimings,
    decide_hotspot_recovery,
)
from services.network_manager import (
    CONNECTED_DEVICE_STATES,
    CONNECTING_DEVICE_STATES,
    NetworkManagerError,
    NetworkManagerService,
)
from services.network_status_tcp import NetworkStatusTcpServer, build_network_status_line
from services.scan_policy import (
    can_pause_hotspot_without_losing_page,
    hotspot_blocks_scan,
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
    "hotspot_active": False,
    "next_action": None,
    "seconds_until_action": None,
    "last_transition_at": None,
    "last_error": None,
}
recovery_lock = Lock()
scan_lock = Lock()
network_operation_lock = RLock()
recovery_runtime = {
    "suspend_until": 0.0,
    "manual_hotspot_until": 0.0,
    "no_access_since": None,
    "last_client_connection": None,
    "last_access_kind": None,
    "wifi_healthy_since": None,
    "lan_connected_since": None,
    "hotspot_active_since": None,
    "last_client_retry_at": None,
}
recovery_timings = RecoveryTimings(
    wifi_client_stable_seconds=config.wifi_client_stable_seconds,
    lan_stable_seconds=config.lan_stable_seconds,
    no_access_hotspot_delay_seconds=config.no_access_hotspot_delay_seconds,
    hotspot_client_retry_interval_seconds=config.hotspot_client_retry_interval_seconds,
    hotspot_minimum_up_seconds=config.hotspot_minimum_up_seconds,
    boot_connection_grace_seconds=config.boot_connection_grace_seconds,
    reconnect_grace_seconds=config.reconnect_grace_seconds,
    disconnect_hotspot_threshold_seconds=config.disconnect_hotspot_threshold_seconds,
)
wifi_scan_state = {
    "state": "idle",
    "message": "Nessuna scansione avviata.",
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


def _request_from_hotspot_network() -> bool:
    remote_addr = request.remote_addr or ""
    try:
        client_address = ipaddress.ip_address(remote_addr)
        hotspot_network = ipaddress.ip_network(config.hotspot_address, strict=False)
    except ValueError:
        return False
    return client_address in hotspot_network


def _can_scan_without_losing_page(status: dict[str, object]) -> bool:
    return can_pause_hotspot_without_losing_page(
        status, _request_from_hotspot_network()
    )


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


def _run_full_wifi_scan_cycle(wifi_interface: str) -> None:
    _set_scan_state(
        state="running",
        message=(
            "Scansione reti in corso: l'hotspot viene spento per pochi secondi "
            "e verra' riattivato automaticamente."
        ),
        started_at=int(time.time()),
        completed_at=None,
        last_error=None,
    )
    _pause_hotspot_recovery(config.hotspot_cooldown_seconds, "manual-full-scan")

    try:
        with network_operation_lock:
            visible_networks = _scan_networks_with_hotspot_paused(wifi_interface)
        _set_scan_state(
            state="completed",
            message=(
                f"Scansione terminata: {len(visible_networks)} reti trovate. "
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
            message="Scansione non riuscita; hotspot riattivato se possibile.",
            completed_at=int(time.time()),
            last_error=detail,
        )


def _scan_networks_with_hotspot_paused(wifi_interface: str | None = None) -> list[dict[str, str]]:
    with network_operation_lock:
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
        transition_changed = (
            updates.get("state", recovery_state["state"]) != recovery_state["state"]
            or updates.get("reason", recovery_state["reason"]) != recovery_state["reason"]
        )
        recovery_state.update(updates)
        if transition_changed or recovery_state["last_transition_at"] is None:
            recovery_state["last_transition_at"] = int(time.time())


def _recovery_state_snapshot() -> dict[str, object]:
    with recovery_lock:
        return dict(recovery_state)


def _pause_hotspot_recovery(seconds: int, reason: str) -> None:
    recovery_runtime["suspend_until"] = max(recovery_runtime["suspend_until"], time.monotonic() + seconds)
    _set_recovery_state(
        state="cooldown",
        reason=reason,
        message=f"Recovery hotspot sospeso per {seconds} secondi.",
        next_action=None,
        seconds_until_action=seconds,
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
        return

    try:
        migrated_connections = network_manager.apply_client_interface_policy()
        if migrated_connections:
            app.logger.info(
                "Profili Wi-Fi associati automaticamente alla radio client: %s",
                ", ".join(migrated_connections),
            )
    except NetworkManagerError as error:
        detail = error.stderr or error.stdout or str(error)
        app.logger.warning(
            "Associazione automatica dei profili Wi-Fi alla radio client non riuscita: %s",
            detail,
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
    scan_limited = hotspot_blocks_scan(status)
    scan_can_pause_safely = _can_scan_without_losing_page(status)
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
            scan_can_pause_safely=scan_can_pause_safely,
            request_via_hotspot=_request_from_hotspot_network(),
            full_scan=_scan_state_snapshot(),
            recovery=_recovery_state_snapshot(),
            manual_hotspot_minutes=max(
                1, config.manual_hotspot_hold_seconds // 60
            ),
            access_sheet=_access_sheet(status),
            error_message=error_message,
            network_message=network_message,
            network_error=network_error,
        ),
        status_code,
    )


def _apply_configuration(payload: dict[str, str]) -> None:
    with network_operation_lock:
        result = network_manager.configure_wifi(payload)
    provisioning_state["state"] = "success" if result.success else "error"
    provisioning_state["message"] = result.message
    provisioning_state["connection_name"] = result.connection_name
    provisioning_state["connectivity"] = result.connectivity
    provisioning_state["interface"] = result.interface
    if result.success:
        recovery_runtime["suspend_until"] = time.monotonic()
    else:
        _pause_hotspot_recovery(
            config.hotspot_cooldown_seconds,
            "post-provisioning-error",
        )


def _wifi_client_is_healthy(status: dict[str, object]) -> bool:
    device_state = str(status.get("device_state", "")).lower()
    active_client_connection = status.get("active_client_connection")
    return bool(active_client_connection) and device_state in CONNECTED_DEVICE_STATES


def _network_is_recovering(status: dict[str, object]) -> bool:
    device_state = str(status.get("device_state", "")).lower()
    return device_state in CONNECTING_DEVICE_STATES


def _elapsed_seconds(started_at: object, now: float) -> int:
    if not isinstance(started_at, (int, float)):
        return 0
    return max(0, int(now - float(started_at)))


def _update_recovery_runtime(status: dict[str, object], now: float) -> None:
    wifi_client_healthy = _wifi_client_is_healthy(status)
    lan_connected = bool(status.get("lan_connected"))
    hotspot_active = bool(status.get("hotspot_active"))

    if wifi_client_healthy:
        if recovery_runtime["wifi_healthy_since"] is None:
            recovery_runtime["wifi_healthy_since"] = now
        recovery_runtime["last_client_connection"] = status.get(
            "active_client_connection"
        )
        recovery_runtime["last_access_kind"] = "wifi"
    else:
        recovery_runtime["wifi_healthy_since"] = None

    if lan_connected:
        if recovery_runtime["lan_connected_since"] is None:
            recovery_runtime["lan_connected_since"] = now
        if not wifi_client_healthy:
            recovery_runtime["last_access_kind"] = "lan"
    else:
        recovery_runtime["lan_connected_since"] = None

    if wifi_client_healthy or lan_connected:
        recovery_runtime["no_access_since"] = None
    elif recovery_runtime["no_access_since"] is None:
        recovery_runtime["no_access_since"] = now

    if hotspot_active:
        if recovery_runtime["hotspot_active_since"] is None:
            recovery_runtime["hotspot_active_since"] = now
    else:
        recovery_runtime["hotspot_active_since"] = None


def _protected_recovery_reason(now: float) -> str | None:
    if provisioning_state["state"] == "running":
        return "provisioning"
    if _scan_state_snapshot().get("state") == "running":
        return "wifi-scan"
    if now < float(recovery_runtime["suspend_until"]):
        return "cooldown"
    return None


def _recovery_observation(
    status: dict[str, object],
    now: float,
) -> RecoveryObservation:
    last_retry_at = recovery_runtime["last_client_retry_at"]
    return RecoveryObservation(
        hotspot_active=bool(status.get("hotspot_active")),
        wifi_client_healthy=_wifi_client_is_healthy(status),
        lan_connected=bool(status.get("lan_connected")),
        has_separate_wifi_interfaces=bool(
            status.get("has_separate_wifi_interfaces")
        ),
        managed_wifi_client_configured=bool(
            status.get("managed_wifi_client_configured")
        ),
        network_recovering=_network_is_recovering(status),
        hotspot_active_for=_elapsed_seconds(
            recovery_runtime["hotspot_active_since"], now
        ),
        wifi_client_stable_for=_elapsed_seconds(
            recovery_runtime["wifi_healthy_since"], now
        ),
        lan_stable_for=_elapsed_seconds(
            recovery_runtime["lan_connected_since"], now
        ),
        no_access_for=_elapsed_seconds(
            recovery_runtime["no_access_since"], now
        ),
        seconds_since_client_retry=(
            _elapsed_seconds(last_retry_at, now)
            if isinstance(last_retry_at, (int, float))
            else None
        ),
        last_access_kind=(
            str(recovery_runtime["last_access_kind"])
            if recovery_runtime["last_access_kind"]
            else None
        ),
        manual_hold_remaining=max(
            0,
            int(float(recovery_runtime["manual_hotspot_until"]) - now),
        ),
        protected_reason=_protected_recovery_reason(now),
    )


def _pending_action(decision: RecoveryDecision) -> str | None:
    if decision.state in {"wifi-stabilizing", "lan-stabilizing"}:
        return "stop-hotspot"
    if decision.state == "waiting-hotspot":
        return "start-hotspot"
    if decision.reason == "single-radio-retry-wait":
        return "retry-client"
    return None


def _publish_recovery_decision(
    decision: RecoveryDecision,
    observation: RecoveryObservation,
) -> None:
    state = decision.state
    _set_recovery_state(
        state=state,
        reason=decision.reason,
        message=decision.message,
        seconds_without_network=observation.no_access_for,
        hotspot_active=observation.hotspot_active,
        next_action=(
            decision.action
            if decision.action != "none"
            else _pending_action(decision)
        ),
        seconds_until_action=decision.seconds_until_action,
        last_error=None,
    )


def _start_hotspot_automatically(now: float) -> None:
    with network_operation_lock:
        network_manager.ensure_hotspot()
    recovery_runtime["hotspot_active_since"] = now
    recovery_runtime["manual_hotspot_until"] = 0.0
    _set_recovery_state(
        state="hotspot-reactivated",
        reason="no-alternate-access",
        message="Pi-Setup attivato automaticamente: nessun accesso alternativo disponibile.",
        seconds_without_network=0,
        hotspot_active=True,
        next_action=None,
        seconds_until_action=None,
        hotspot_reactivation_count=int(
            recovery_state["hotspot_reactivation_count"]
        )
        + 1,
        last_error=None,
    )


def _stop_hotspot_for_stable_access(
    status: dict[str, object],
    reason: str,
) -> None:
    reconnected_profile: str | None = None
    with network_operation_lock:
        network_manager.stop_hotspot()
        if (
            not _wifi_client_is_healthy(status)
            and bool(status.get("managed_wifi_client_configured"))
        ):
            reconnected_profile = network_manager.reconnect_managed_wifi(
                str(status.get("client_wifi_interface") or config.client_wifi_interface),
                preferred_connection=(
                    str(recovery_runtime["last_client_connection"])
                    if recovery_runtime["last_client_connection"]
                    else None
                ),
            )

    recovery_runtime["hotspot_active_since"] = None
    recovery_runtime["manual_hotspot_until"] = 0.0
    message = "Pi-Setup spento automaticamente: collegamento alternativo stabile."
    if reconnected_profile:
        message += f" Riconnesso il profilo {reconnected_profile}."
    _set_recovery_state(
        state="hotspot-stopped",
        reason=reason,
        message=message,
        hotspot_active=False,
        next_action=None,
        seconds_until_action=None,
        last_error=None,
    )


def _retry_single_radio_client(status: dict[str, object], now: float) -> None:
    recovery_runtime["last_client_retry_at"] = now
    _set_recovery_state(
        state="retrying-client",
        reason="single-radio-client-retry",
        message="Pi-Setup sospeso brevemente: tentativo di connessione Wi-Fi salvata.",
        hotspot_active=False,
        next_action=None,
        seconds_until_action=None,
        last_error=None,
    )

    connection_name: str | None = None
    retry_error: NetworkManagerError | None = None
    with network_operation_lock:
        try:
            network_manager.stop_hotspot()
            recovery_runtime["hotspot_active_since"] = None
            connection_name = network_manager.reconnect_managed_wifi(
                str(status.get("client_wifi_interface") or config.client_wifi_interface),
                preferred_connection=(
                    str(recovery_runtime["last_client_connection"])
                    if recovery_runtime["last_client_connection"]
                    else None
                ),
            )
        except NetworkManagerError as error:
            retry_error = error

        if connection_name is None:
            network_manager.ensure_hotspot()

    if connection_name:
        recovered_at = time.monotonic()
        recovery_runtime["wifi_healthy_since"] = recovered_at
        recovery_runtime["last_client_connection"] = connection_name
        recovery_runtime["last_access_kind"] = "wifi"
        recovery_runtime["no_access_since"] = None
        _set_recovery_state(
            state="client-recovered",
            reason="single-radio-client-recovered",
            message=f"Connessione Wi-Fi ripristinata con il profilo {connection_name}.",
            hotspot_active=False,
            next_action=None,
            seconds_until_action=None,
            last_error=None,
        )
        return

    recovery_runtime["hotspot_active_since"] = time.monotonic()
    detail = ""
    if retry_error:
        detail = retry_error.stderr or retry_error.stdout or str(retry_error)
    _set_recovery_state(
        state="hotspot-restored",
        reason="single-radio-client-retry-failed",
        message="Rete salvata non disponibile: Pi-Setup e' stato riattivato.",
        hotspot_active=True,
        next_action="retry-client",
        seconds_until_action=config.hotspot_client_retry_interval_seconds,
        last_error=detail or None,
    )


def _run_recovery_monitor() -> None:
    while True:
        now = time.monotonic()

        try:
            status = network_manager.current_status()
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

        _update_recovery_runtime(status, now)
        observation = _recovery_observation(status, now)
        decision = decide_hotspot_recovery(observation, recovery_timings)
        _publish_recovery_decision(decision, observation)

        try:
            if decision.action == "start-hotspot":
                _start_hotspot_automatically(now)
            elif decision.action == "stop-hotspot":
                _stop_hotspot_for_stable_access(status, decision.reason)
            elif decision.action == "retry-client":
                _retry_single_radio_client(status, now)
        except NetworkManagerError as error:
            detail = error.stderr or error.stdout or str(error)
            if decision.action == "retry-client":
                try:
                    network_manager.ensure_hotspot()
                    recovery_runtime["hotspot_active_since"] = time.monotonic()
                except NetworkManagerError:
                    pass
            _set_recovery_state(
                state="warning",
                reason=f"{decision.action}-failed",
                message="Operazione automatica hotspot non riuscita; nuovo tentativo al prossimo ciclo.",
                last_error=detail,
                seconds_without_network=observation.no_access_for,
                next_action=decision.action,
                seconds_until_action=config.recovery_check_interval_seconds,
            )

        time.sleep(config.recovery_check_interval_seconds)


def _start_background_threads() -> None:
    if config.auto_recovery_enabled:
        monitor = Thread(target=_run_recovery_monitor, daemon=True, name="hotspot-recovery")
        monitor.start()

    if config.network_status_tcp_enabled:
        status_server = NetworkStatusTcpServer(
            lambda: build_network_status_line(network_manager.tcp_status_snapshot()),
            port=config.network_status_tcp_port,
            interval_seconds=config.network_status_tcp_interval_seconds,
            logger=app.logger,
        )
        tcp_thread = Thread(
            target=status_server.serve_forever,
            daemon=True,
            name="network-status-tcp",
        )
        tcp_thread.start()


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
        recovery=_recovery_state_snapshot(),
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
            "recovery": _recovery_state_snapshot(),
            "full_scan": _scan_state_snapshot(),
        }
    )


@app.get("/api/networks")
def api_networks():
    status = network_manager.current_status()
    wifi_interface = (
        request.args.get("wifi_interface", "").strip()
        or str(status.get("client_wifi_interface") or config.client_wifi_interface)
    )
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
                    "message": "Scansione eseguita tramite LAN cablata.",
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
    payload = request.get_json(silent=True) or request.form
    wifi_interface = (
        str(payload.get("wifi_interface", "")).strip()
        or str(status.get("client_wifi_interface") or config.client_wifi_interface)
    )
    if wifi_interface not in status.get("wifi_interface_names", []):
        return jsonify(
            {
                "ok": False,
                "error": "invalid-wifi-interface",
                "message": "Seleziona una interfaccia Wi-Fi valida.",
            }
        ), 400

    if not hotspot_blocks_scan(status, wifi_interface):
        return jsonify(
            {
                "ok": False,
                "error": "full-scan-not-needed",
                "message": "La radio selezionata non richiede lo spegnimento temporaneo dell'hotspot.",
            }
        ), 400

    current_scan = _scan_state_snapshot()
    if current_scan.get("state") == "running":
        return jsonify({"ok": True, "scan": current_scan})

    worker = Thread(
        target=_run_full_wifi_scan_cycle,
        args=(wifi_interface,),
        daemon=True,
        name=f"wifi-full-scan-{wifi_interface}",
    )
    worker.start()
    return jsonify(
        {
            "ok": True,
            "scan": _scan_state_snapshot(),
            "message": (
                f"Scansione avviata su {wifi_interface}. "
                f"Il telefono perdera' {config.hotspot_ssid} per alcuni secondi."
            ),
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
    target_interface = payload.get("wifi_interface", "")
    if target_interface == config.hotspot_interface:
        provisioning_state["message"] = (
            "Il dispositivo sta disattivando l'hotspot temporaneo "
            "e sta provando la nuova rete."
        )
    else:
        provisioning_state["message"] = (
            "Il dispositivo sta provando la nuova rete sulla radio client; "
            "Pi-Setup restera' attivo fino alla verifica della connessione."
        )
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
    return jsonify(_recovery_state_snapshot())


@app.post("/hotspot/restart")
def restart_hotspot():
    now = time.monotonic()
    try:
        with network_operation_lock:
            network_manager.ensure_hotspot()
    except NetworkManagerError as error:
        detail = error.stderr or error.stdout or str(error)
        if request.is_json:
            return jsonify({"ok": False, "message": detail}), 500
        return _render_index(network_error=detail, status_code=500)

    recovery_runtime["hotspot_active_since"] = now
    recovery_runtime["manual_hotspot_until"] = (
        now + config.manual_hotspot_hold_seconds
    )
    _set_recovery_state(
        state="manual-hotspot",
        reason="manual-hold",
        message="Pi-Setup attivato manualmente.",
        hotspot_active=True,
        next_action="automatic-management",
        seconds_until_action=config.manual_hotspot_hold_seconds,
        last_error=None,
    )
    if request.is_json:
        return jsonify({"ok": True, "status": network_manager.current_status()})
    return _render_index(
        network_message=(
            "Pi-Setup attivato manualmente per "
            f"{config.manual_hotspot_hold_seconds // 60} minuti."
        )
    )


@app.post("/hotspot/stop")
def stop_hotspot():
    status = network_manager.current_status()
    alternate_access = bool(status.get("lan_connected")) or (
        _wifi_client_is_healthy(status)
        and status.get("active_client_interface")
        != status.get("hotspot_interface")
    )
    if not alternate_access:
        message = (
            "Pi-Setup non puo' essere spento manualmente: "
            "non e' disponibile un collegamento LAN o Wi-Fi alternativo."
        )
        if request.is_json:
            return jsonify({"ok": False, "message": message}), 409
        return _render_index(network_error=message, status_code=409)

    with network_operation_lock:
        network_manager.stop_hotspot()
    recovery_runtime["hotspot_active_since"] = None
    recovery_runtime["manual_hotspot_until"] = 0.0
    _set_recovery_state(
        state="hotspot-stopped",
        reason="manual-stop",
        message="Pi-Setup spento manualmente; collegamento alternativo disponibile.",
        hotspot_active=False,
        next_action=None,
        seconds_until_action=None,
        last_error=None,
    )
    if request.is_json:
        return jsonify({"ok": True, "status": network_manager.current_status()})
    return _render_index(network_message="Pi-Setup spento manualmente.")


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
