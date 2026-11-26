"""
Rutas CRUD para Administración de Dispositivos.
"""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models.audit import AuditLog
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.router_event import RouterSyncLog
from app.models.user import utc_now_naive
from app.routes.decorators import write_permission_required
from app.services.category_service import get_category_options
from app.services.device_service import create_device, delete_device, update_device
from app.services.intermediary_proxy import bump_proxy_policy_version
from app.services.network_probe_service import detect_local_network_info
from app.services.router_adapter import execute_device_router_sync, get_router_adapter
from app.services.validators import ValidationError

devices_bp = Blueprint("devices", __name__, url_prefix="/devices")


@devices_bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    type_filter = (request.args.get("device_type") or "").strip()
    profile_filter = (request.args.get("profile") or "").strip()
    sync_filter = (request.args.get("sync_status") or "").strip()

    query = Device.query

    if q:
        like_expr = f"%{q}%"
        query = query.filter(
            db.or_(
                Device.name.ilike(like_expr),
                Device.internal_code.ilike(like_expr),
                Device.ip_address.ilike(like_expr),
                Device.mac_address.ilike(like_expr),
                Device.hostname.ilike(like_expr),
                Device.owner_label.ilike(like_expr),
            )
        )
    if status_filter in Device.VALID_ADMIN_STATUSES:
        query = query.filter(Device.admin_status == status_filter)
    if type_filter in Device.VALID_TYPES:
        query = query.filter(Device.device_type == type_filter)
    if profile_filter in Device.VALID_PROFILES:
        query = query.filter(Device.profile == profile_filter)
    if sync_filter in Device.VALID_ROUTER_SYNC:
        query = query.filter(Device.router_sync_status == sync_filter)

    devices = query.order_by(Device.created_at.desc()).all()
    adapter_info = get_router_adapter().get_diagnostics()

    return render_template(
        "devices/index.html",
        devices=devices,
        q=q,
        status_filter=status_filter,
        type_filter=type_filter,
        profile_filter=profile_filter,
        sync_filter=sync_filter,
        device_Model=Device,
        adapter_info=adapter_info,
    )


@devices_bp.route("/new", methods=["GET", "POST"])
@login_required
@write_permission_required
def create():
    configured_scope = current_app.config.get("DEFAULT_NETWORK_SCOPE", "192.168.1.0/24")
    prefill_ip = (request.args.get("ip") or "").strip()
    prefill_mac = (request.args.get("mac") or "").strip()
    prefill_hostname = (request.args.get("hostname") or "").strip()
    prefill_name = (request.args.get("name") or "").strip()
    prefill_type = (request.args.get("device_type") or "").strip()
    prefill_scope = (request.args.get("scope") or "").strip()

    # Detectar subred Wi-Fi activa en GET cuando no hay una subred explícita y no estamos usando datos fijos
    active_net = detect_local_network_info() if request.method == "GET" else None
    if prefill_scope:
        default_scope = prefill_scope
    elif active_net and active_net.get("is_lan_reachable"):
        default_scope = active_net["network_scope"]
    else:
        default_scope = configured_scope

    prefix_source = prefill_ip or (active_net.get("local_ip") if active_net and active_net.get("is_lan_reachable") else "")
    if prefix_source and "." in prefix_source:
        default_ip_prefix = ".".join(prefix_source.split(".")[:3]) + "."
    else:
        default_ip_prefix = ".".join(default_scope.split("/")[0].split(".")[:3]) + "."

    device_types = get_category_options("device_type")
    device_profiles = get_category_options("device_profile")
    admin_statuses = get_category_options("admin_status")

    form_data = {
        "name": prefill_name,
        "ip_address": prefill_ip,
        "mac_address": prefill_mac,
        "hostname": prefill_hostname,
        "network_scope": default_scope,
        "ip_assignment_type": "dhcp_reservation",
        "device_type": prefill_type if prefill_type in Device.VALID_TYPES else "smartphone" if prefill_ip else "workstation",
        "profile": "family",
        "admin_status": "authorized",
    }

    if request.method == "POST":
        form_data = request.form.to_dict()
        sync_now = request.form.get("sync_with_adapter") == "1"
        try:
            device = create_device(form_data, user_id=current_user.id, is_demo=False)
            if sync_now:
                sync_res = execute_device_router_sync(device, triggered_by_id=current_user.id)
                flash(
                    f"Dispositivo '{device.name}' ({device.internal_code}) registrado y procesado "
                    f"por el adaptador: {sync_res.response_detail}",
                    "success",
                )
            else:
                flash(
                    f"Dispositivo '{device.name}' ({device.internal_code}) registrado en la base de datos "
                    "(Pendiente de aplicar en adaptador de red).",
                    "success",
                )
            return redirect(url_for("devices.detail", device_id=device.id))
        except ValidationError as exc:
            flash(str(exc), "error")
            return (
                render_template(
                    "devices/form.html",
                    device=None,
                    form_data=form_data,
                    device_types=device_types,
                    device_profiles=device_profiles,
                    admin_statuses=admin_statuses,
                    device_Model=Device,
                    default_ip_prefix=default_ip_prefix,
                ),
                400,
            )

    return render_template(
        "devices/form.html",
        device=None,
        form_data=form_data,
        device_types=device_types,
        device_profiles=device_profiles,
        admin_statuses=admin_statuses,
        device_Model=Device,
        default_ip_prefix=default_ip_prefix,
    )


@devices_bp.route("/<int:device_id>", methods=["GET", "POST"])
@login_required
def detail(device_id: int):
    """
    Vista unificada de Ficha Técnica del Dispositivo con Editor Integrado y Control Familiar.
    Permite consultar especificaciones técnicas, auditar eventos y editar parámetros
    de red directamente en la misma pantalla sin cambiar de contexto.
    """
    device = db.get_or_404(Device, device_id)
    device_types = get_category_options("device_type")
    device_profiles = get_category_options("device_profile")
    admin_statuses = get_category_options("admin_status")
    active_tab = request.args.get("tab", "family" if current_user.is_operator else "ficha")

    form_data = {
        "name": device.name,
        "hostname": device.hostname or "",
        "ip_address": device.ip_address,
        "network_scope": device.network_scope,
        "ip_assignment_type": device.ip_assignment_type,
        "mac_address": device.mac_address or "",
        "device_type": device.device_type,
        "profile": getattr(device, "profile", "family") or "family",
        "owner_label": device.owner_label or "",
        "description": device.description or "",
        "admin_status": device.admin_status,
    }

    # Procesar edición integrada en la ficha técnica
    if request.method == "POST":
        if not current_user.is_admin:
            flash("Solo los Administradores de Red y Superadministradores pueden modificar parámetros técnicos.", "warning")
            return redirect(url_for("devices.detail", device_id=device.id, tab="family" if current_user.is_operator else "ficha"))

        form_data = request.form.to_dict()
        sync_now = request.form.get("sync_with_adapter") == "1"
        try:
            update_device(device, form_data, user_id=current_user.id)
            if device.admin_status in ("authorized", "blocked"):
                prev_auto = AccessPolicy.query.filter_by(
                    device_id=device.id,
                    observations="[AUTO_FAMILY_CONTROL]",
                    status="active",
                ).all()
                for p in prev_auto:
                    p.status = "revoked"
                if prev_auto:
                    db.session.commit()
                    bump_proxy_policy_version()
            if sync_now:
                sync_res = execute_device_router_sync(device, triggered_by_id=current_user.id)
                flash(
                    f"Ficha técnica de '{device.name}' actualizada y sincronizada: {sync_res.response_detail}",
                    "success",
                )
            else:
                flash(f"Parámetros del dispositivo '{device.name}' guardados exitosamente.", "success")
            return redirect(url_for("devices.detail", device_id=device.id, tab="ficha"))
        except ValidationError as exc:
            flash(str(exc), "error")
            active_tab = "editor"

    audit_history = (
        AuditLog.query.filter_by(target_type="device", target_id=str(device.id))
        .order_by(AuditLog.created_at.desc())
        .limit(15)
        .all()
    )
    sync_logs = (
        RouterSyncLog.query.filter_by(device_id=device.id)
        .order_by(RouterSyncLog.created_at.desc())
        .limit(10)
        .all()
    )
    adapter_info = get_router_adapter().get_diagnostics()

    family_mode = "allow"
    if device.admin_status == "blocked":
        family_mode = "block"
    elif device.admin_status == "pending":
        family_mode = "pending"
    elif device.admin_status == "restricted":
        active_auto_policy = (
            AccessPolicy.query.filter_by(
                device_id=device.id,
                observations="[AUTO_FAMILY_CONTROL]",
                status="active",
            )
            .order_by(AccessPolicy.id.desc())
            .first()
        )
        if active_auto_policy and active_auto_policy.action == "restrict":
            family_mode = "study"
        else:
            family_mode = "pause"

    return render_template(
        "devices/detail.html",
        device=device,
        form_data=form_data,
        active_tab=active_tab,
        family_mode=family_mode,
        device_types=device_types,
        device_profiles=device_profiles,
        admin_statuses=admin_statuses,
        audit_history=audit_history,
        sync_logs=sync_logs,
        adapter_info=adapter_info,
        device_Model=Device,
    )


@devices_bp.route("/<int:device_id>/family-access", methods=["POST"])
@login_required
@write_permission_required
def family_access(device_id: int):
    """
    Control Familiar Amigable de Conexión (enfocado en roles Operador y padres de familia).
    Permite modular el acceso de un equipo con un solo clic sin necesidad de conocer términos de redes.
    """
    device = db.get_or_404(Device, device_id)
    mode = (request.form.get("mode") or "allow").strip()

    mode_map = {
        "allow": ("authorized", "Internet Libre (Acceso Total para la Familia)"),
        "pause": ("restricted", "Pausa Temporal de Internet (Comida / Hora de Dormir)"),
        "study": ("restricted", "Modo Estudio (Solo Tareas y Páginas Educativas)"),
        "block": ("blocked", "Internet Apagado / Bloqueado"),
    }

    if mode not in mode_map:
        flash("Modo de acceso familiar no reconocido.", "error")
        return redirect(url_for("devices.detail", device_id=device.id))

    new_status, label = mode_map[mode]
    old_status = device.admin_status
    device.admin_status = new_status

    # Revocar politicas previas autogestionadas de Control Familiar antes de aplicar la nueva
    prev_auto = AccessPolicy.query.filter_by(
        device_id=device.id,
        observations="[AUTO_FAMILY_CONTROL]",
        status="active",
    ).all()
    for p in prev_auto:
        p.status = "revoked"

    # Crear politica especifica de Control Familiar para que el Intermediario aplique Pausa vs Estudio en tiempo real
    if mode in ("pause", "study"):
        now_utc = utc_now_naive()
        is_pause = mode == "pause"
        auto_policy = AccessPolicy(
            name="Control Familiar: Pausa Temporal" if is_pause else "Control Familiar: Modo Estudio",
            description=(
                "Pausa total temporal activada desde el Control Familiar."
                if is_pause
                else "Restriccion de sitios recreativos y video permitiendo portales escolares."
            ),
            device_id=device.id,
            policy_type="administrative_auth" if is_pause else "navigation_restriction",
            action="block" if is_pause else "restrict",
            priority=1,
            status="active",
            valid_from=now_utc,
            valid_until=None,
            navigation_profile=None if is_pause else "Modo Estudio (Solo tareas y portales educativos)",
            target_scope="all_traffic" if is_pause else "web_category",
            observations="[AUTO_FAMILY_CONTROL]",
            enforcement_status="simulated_in_lab",
            last_evaluated_at=now_utc,
            is_demo=device.is_demo,
            created_by_id=current_user.id,
        )
        db.session.add(auto_policy)

    db.session.commit()
    bump_proxy_policy_version()

    sync_res = execute_device_router_sync(device, triggered_by_id=current_user.id, commit=True)

    from app.services.audit_service import log_audit_event
    log_audit_event(
        event_type="FAMILY_ACCESS_CHANGED",
        module="devices",
        description=(
            f"El usuario '{current_user.username}' ({current_user.role_label}) cambió el acceso familiar de "
            f"'{device.name}' a: {label}."
        ),
        severity="info",
        user_id=current_user.id,
        target_type="device",
        target_id=device.id,
        metadata={"mode": mode, "old_status": old_status, "new_status": new_status},
        commit=True,
    )

    flash(f"Control Familiar: El acceso de '{device.name}' ahora está en: {label}.", "success")
    return redirect(url_for("devices.detail", device_id=device.id, tab="family"))


@devices_bp.route("/<int:device_id>/edit", methods=["GET", "POST"])
@login_required
@write_permission_required
def edit(device_id: int):
    """Ruta de compatibilidad que redirige a la ficha técnica con la pestaña de edición abierta."""
    return redirect(url_for("devices.detail", device_id=device_id, tab="editor"))


@devices_bp.route("/<int:device_id>/sync", methods=["POST"])
@login_required
@write_permission_required
def sync_router(device_id: int):
    device = db.get_or_404(Device, device_id)
    res = execute_device_router_sync(device, triggered_by_id=current_user.id)
    flash(res.response_detail, "info" if not res.is_simulated else "success")
    return redirect(request.referrer or url_for("devices.detail", device_id=device.id))


@devices_bp.route("/<int:device_id>/delete", methods=["POST"])
@login_required
@write_permission_required
def delete(device_id: int):
    device = db.get_or_404(Device, device_id)
    dev_name = device.name
    dev_code = device.internal_code
    try:
        delete_device(device, user_id=current_user.id)
        flash(
            f"El dispositivo '{dev_name}' ({dev_code}) y sus registros asociados fueron eliminados.",
            "info",
        )
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("devices.index"))

