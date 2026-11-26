"""
Rutas del Monitor de Red en Tiempo Real y Portal de Verificación de Acceso.

Permite detectar la subred activa de un módem o mini-módem portátil con chip,
descubrir equipos conectados mediante ARP/ICMP, realizar pruebas Ping en vivo,
generar códigos QR de conexión móvil y consultar en tiempo real el estado de
acceso efectivo aplicado por NetGuard a cada dirección IP.
"""

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models.device import Device
from app.routes.decorators import write_permission_required
from app.services.audit_service import log_audit_event
from app.services.intermediary_proxy import get_proxy_status
from app.services.network_probe_service import (
    build_wifi_qr_svg,
    detect_local_network_info,
    evaluate_live_device_access,
    ping_host,
    scan_active_network,
)
from app.services.validators import ValidationError, validate_and_normalize_ip, validate_network_scope

network_bp = Blueprint("network", __name__, url_prefix="/network")


def _resolve_client_ip() -> str:
    """Obtiene la dirección IP real del cliente HTTP que realiza la petición."""
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded or request.remote_addr or "127.0.0.1"


@network_bp.route("/")
@login_required
def monitor():
    """Vista principal del Monitor de Red en Tiempo Real y Enlace Móvil QR."""
    net_info = detect_local_network_info()
    quick_arp = scan_active_network(include_ping_sweep=False)
    devices = Device.query.order_by(Device.is_demo.asc(), Device.name.asc()).all()
    proxy_status = get_proxy_status()

    return render_template(
        "network/monitor.html",
        net_info=net_info,
        initial_scan=quick_arp,
        devices=devices,
        proxy_status=proxy_status,
        configured_scope=current_app.config.get("DEFAULT_NETWORK_SCOPE", "192.168.1.0/24"),
        configured_gateway=current_app.config.get("DEFAULT_GATEWAY_IP", "192.168.1.1"),
    )


@network_bp.route("/proxy-logs")
@login_required
def proxy_logs():
    """Devuelve las ultimas conexiones evaluadas en vivo por el Proxy Intermediario."""
    return jsonify({"success": True, **get_proxy_status()})


@network_bp.route("/wifi-qr", methods=["POST"])
@login_required
def wifi_qr():
    """Genera un codigo QR estandar de conexion Wi-Fi sin almacenar ni registrar la contrasena."""
    payload = request.get_json(silent=True) or request.form
    ssid = (payload.get("ssid") or "").strip()
    password = payload.get("password") or ""
    security = (payload.get("security") or "WPA").strip()

    if not ssid or len(ssid) > 64:
        return jsonify({"success": False, "error": "Ingrese el nombre de la red Wi-Fi (SSID)."}), 400
    if security != "nopass" and not password:
        return jsonify({"success": False, "error": "Ingrese la contrasena del Wi-Fi o seleccione Sin contrasena."}), 400

    svg = build_wifi_qr_svg(ssid=ssid, password=password, security=security)
    if not svg:
        return jsonify({"success": False, "error": "No fue posible generar el QR Wi-Fi."}), 500

    return jsonify({"success": True, "ssid": ssid, "qr_svg": svg})


@network_bp.route("/proxy.pac")
def proxy_pac():
    """
    Entrega un archivo Proxy Auto-Config (PAC) estandar para configurar con una sola URL
    el Intermediario Proxy en Android, iOS o equipos de la red sin tocar el portal local.
    """
    net_info = detect_local_network_info()
    proxy_status = get_proxy_status()
    local_ip = net_info["local_ip"]
    proxy_port = proxy_status["port"]
    pac_body = (
        "function FindProxyForURL(url, host) {\n"
        '  if (isPlainHostName(host) || shExpMatch(host, "127.*") || '
        f'host == "localhost" || host == "{local_ip}") {{\n'
        '    return "DIRECT";\n'
        "  }\n"
        f'  return "PROXY {local_ip}:{proxy_port}; DIRECT";\n'
        "}\n"
    )
    return Response(pac_body, mimetype="application/x-ns-proxy-autoconfig")


@network_bp.route("/scan", methods=["POST"])
@login_required
def scan():
    """Ejecuta un escaneo completo (barrido ICMP + caché ARP) sobre la red Wi-Fi activa."""
    result = scan_active_network(include_ping_sweep=True)
    if current_user.can_modify:
        log_audit_event(
            event_type="NETWORK_LIVE_SCAN",
            module="devices",
            description=(
                f"Escaneo en vivo sobre subred {result['network_info']['scan_cidr']}: "
                f"{result['online_count']} equipo(s) en línea detectado(s)."
            ),
            severity="info",
            user_id=current_user.id,
            metadata={
                "scan_cidr": result["network_info"]["scan_cidr"],
                "online_count": result["online_count"],
                "total_discovered": len(result["discovered"]),
            },
            commit=True,
        )
    return jsonify({"success": True, **result})


@network_bp.route("/ping", methods=["POST"])
@login_required
def ping_device():
    """Realiza una prueba de conectividad ICMP en tiempo real contra una IP específica."""
    payload = request.get_json(silent=True) or request.form
    ip_raw = (payload.get("ip_address") or "").strip()
    device_id = payload.get("device_id")
    record_audit = str(payload.get("record_audit", "")).lower() in ("1", "true", "yes")

    try:
        ip_clean = validate_and_normalize_ip(ip_raw)
    except ValidationError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    res = ping_host(ip_clean, timeout_ms=900)

    if record_audit and current_user.can_modify:
        dev_label = ip_clean
        if device_id:
            dev = db.session.get(Device, int(device_id))
            if dev:
                dev_label = f"{dev.name} ({dev.ip_address})"
        log_audit_event(
            event_type="LIVE_PING_CHECK",
            module="devices",
            description=f"Comprobación ICMP en tiempo real hacia {dev_label}: {res['detail']}.",
            severity="info",
            user_id=current_user.id,
            target_type="device" if device_id else None,
            target_id=device_id if device_id else None,
            metadata=res,
            commit=True,
        )

    return jsonify({"success": True, **res})


@network_bp.route("/adopt-subnet", methods=["POST"])
@login_required
@write_permission_required
def adopt_subnet():
    """
    Adapta en caliente el ámbito de red y puerta de enlace predeterminados del sistema
    a la subred del módem o mini-módem conectado actualmente.
    """
    net_info = detect_local_network_info()
    try:
        new_scope = validate_network_scope(net_info["network_scope"])
    except ValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("network.monitor"))

    new_gateway = net_info["gateway_ip"]
    current_app.config["DEFAULT_NETWORK_SCOPE"] = new_scope
    current_app.config["DEFAULT_GATEWAY_IP"] = new_gateway

    log_audit_event(
        event_type="NETWORK_SCOPE_ADOPTED",
        module="system",
        description=(
            f"Subred predeterminada adaptada a la red activa del módem/Wi-Fi: "
            f"{new_scope} (Gateway: {new_gateway})."
        ),
        severity="info",
        user_id=current_user.id,
        metadata={"network_scope": new_scope, "gateway_ip": new_gateway},
        commit=True,
    )
    flash(
        f"Ámbito predeterminado adaptado a la red conectada: {new_scope} (Puerta de enlace: {new_gateway}).",
        "success",
    )
    return redirect(url_for("network.monitor"))


@network_bp.route("/mi-acceso")
def client_status():
    """
    Vista móvil ligera de verificación de acceso en tiempo real.
    Permite a cualquier teléfono conectado al mini-módem consultar qué regla, horario
    o fase de intermitencia aplica NetGuard en este preciso momento sobre su IP real.
    """
    client_ip = _resolve_client_ip()
    requested_ip = (request.args.get("ip") or "").strip()

    # Solo usuarios autenticados pueden simular/inspeccionar otra IP distinta a la suya propia
    if requested_ip and current_user.is_authenticated:
        try:
            target_ip = validate_and_normalize_ip(requested_ip)
        except ValidationError:
            target_ip = client_ip
    else:
        target_ip = client_ip

    evaluation = evaluate_live_device_access(target_ip)
    devices = (
        Device.query.order_by(Device.is_demo.asc(), Device.name.asc()).all()
        if current_user.is_authenticated
        else []
    )
    return render_template(
        "network/client_status.html",
        evaluation=evaluation,
        client_ip=client_ip,
        target_ip=target_ip,
        devices=devices,
    )


@network_bp.route("/api/evaluate")
def api_evaluate():
    """Endpoint JSON ligero para refresco automático del estado en tiempo real desde teléfonos."""
    client_ip = _resolve_client_ip()
    requested_ip = (request.args.get("ip") or "").strip()

    if requested_ip and current_user.is_authenticated:
        try:
            target_ip = validate_and_normalize_ip(requested_ip)
        except ValidationError:
            target_ip = client_ip
    else:
        target_ip = client_ip

    evaluation = evaluate_live_device_access(target_ip)
    return jsonify({"success": True, **evaluation})
