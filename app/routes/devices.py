"""
Rutas CRUD para Administración de Dispositivos.
"""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models.audit import AuditLog
from app.models.device import Device
from app.models.router_event import RouterSyncLog
from app.routes.decorators import write_permission_required
from app.services.category_service import get_category_options
from app.services.device_service import create_device, delete_device, update_device
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
    default_scope = current_app.config.get("DEFAULT_NETWORK_SCOPE", "192.168.1.0/24")
    device_types = get_category_options("device_type")
    device_profiles = get_category_options("device_profile")
    admin_statuses = get_category_options("admin_status")

    form_data = {
        "network_scope": default_scope,
        "ip_assignment_type": "dhcp_reservation",
        "device_type": "workstation",
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

    return render_template(
        "devices/detail.html",
        device=device,
        form_data=form_data,
        active_tab=active_tab,
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
    db.session.commit()

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

