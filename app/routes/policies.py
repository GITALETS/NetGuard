"""
Rutas CRUD para Administración de Políticas de Acceso.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.router_event import RouterSyncLog
from app.models.user import utc_now_naive
from app.routes.decorators import write_permission_required
from app.services.policy_service import (
    create_policy,
    delete_policy,
    refresh_expired_policies,
    update_policy,
)
from app.services.router_adapter import execute_policy_router_sync, get_router_adapter
from app.services.validators import ValidationError

policies_bp = Blueprint("policies", __name__, url_prefix="/policies")


@policies_bp.route("/")
@login_required
def index():
    now_utc = utc_now_naive()
    refresh_expired_policies(now_utc)

    device_id = request.args.get("device_id", type=int)
    type_filter = (request.args.get("policy_type") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    enforcement_filter = (request.args.get("enforcement_status") or "").strip()

    query = AccessPolicy.query
    if device_id:
        query = query.filter(AccessPolicy.device_id == device_id)
    if type_filter in AccessPolicy.VALID_POLICY_TYPES:
        query = query.filter(AccessPolicy.policy_type == type_filter)
    if enforcement_filter in AccessPolicy.VALID_ENFORCEMENT:
        query = query.filter(AccessPolicy.enforcement_status == enforcement_filter)

    policies = query.order_by(AccessPolicy.priority.asc(), AccessPolicy.created_at.desc()).all()
    if status_filter:
        policies = [p for p in policies if p.effective_status_at(now_utc) == status_filter]

    devices = Device.query.order_by(Device.name.asc()).all()
    adapter_info = get_router_adapter().get_diagnostics()

    return render_template(
        "policies/index.html",
        policies=policies,
        devices=devices,
        device_id=device_id,
        type_filter=type_filter,
        status_filter=status_filter,
        enforcement_filter=enforcement_filter,
        policy_Model=AccessPolicy,
        adapter_info=adapter_info,
    )


@policies_bp.route("/new", methods=["GET", "POST"])
@login_required
@write_permission_required
def create():
    devices = Device.query.order_by(Device.name.asc()).all()
    if not devices:
        flash("Antes de crear una política de acceso, debe registrar al menos un dispositivo.", "warning")
        return redirect(url_for("devices.create"))

    now_str = utc_now_naive().strftime("%Y-%m-%dT%H:%M")
    preselected_device_id = request.args.get("device_id", type=int) or devices[0].id

    form_data = {
        "device_id": preselected_device_id,
        "policy_type": "administrative_auth",
        "action": "allow",
        "priority": 50,
        "status": "active",
        "valid_from": now_str,
        "valid_until": "",
        "navigation_profile": "",
        "description": "",
        "observations": "",
    }

    if request.method == "POST":
        form_data = request.form.to_dict()
        sync_now = request.form.get("sync_with_adapter") == "1"
        try:
            policy = create_policy(form_data, user_id=current_user.id, is_demo=False)
            if sync_now:
                sync_res = execute_policy_router_sync(policy, triggered_by_id=current_user.id)
                flash(
                    f"Política '{policy.name}' creada y procesada en adaptador: {sync_res.response_detail}",
                    "success",
                )
            else:
                flash(
                    f"Política '{policy.name}' registrada en la base de datos "
                    "(No aplicada al router hasta sincronizar).",
                    "success",
                )
            return redirect(url_for("policies.detail", policy_id=policy.id))
        except ValidationError as exc:
            flash(str(exc), "error")
            return (
                render_template(
                    "policies/form.html",
                    policy=None,
                    devices=devices,
                    form_data=form_data,
                    policy_Model=AccessPolicy,
                ),
                400,
            )

    return render_template(
        "policies/form.html",
        policy=None,
        devices=devices,
        form_data=form_data,
        policy_Model=AccessPolicy,
    )


@policies_bp.route("/<int:policy_id>")
@login_required
def detail(policy_id: int):
    refresh_expired_policies()
    policy = db.get_or_404(AccessPolicy, policy_id)
    sync_logs = (
        RouterSyncLog.query.filter_by(policy_id=policy.id)
        .order_by(RouterSyncLog.created_at.desc())
        .limit(10)
        .all()
    )
    adapter_info = get_router_adapter().get_diagnostics()
    return render_template(
        "policies/detail.html",
        policy=policy,
        sync_logs=sync_logs,
        adapter_info=adapter_info,
    )


@policies_bp.route("/<int:policy_id>/edit", methods=["GET", "POST"])
@login_required
@write_permission_required
def edit(policy_id: int):
    policy = db.get_or_404(AccessPolicy, policy_id)
    devices = Device.query.order_by(Device.name.asc()).all()

    form_data = {
        "name": policy.name,
        "description": policy.description or "",
        "device_id": policy.device_id,
        "policy_type": policy.policy_type,
        "action": policy.action,
        "priority": policy.priority,
        "status": policy.status,
        "valid_from": policy.valid_from.strftime("%Y-%m-%dT%H:%M") if policy.valid_from else "",
        "valid_until": policy.valid_until.strftime("%Y-%m-%dT%H:%M") if policy.valid_until else "",
        "navigation_profile": policy.navigation_profile or "",
        "observations": policy.observations or "",
    }

    if request.method == "POST":
        form_data = request.form.to_dict()
        sync_now = request.form.get("sync_with_adapter") == "1"
        try:
            update_policy(policy, form_data, user_id=current_user.id)
            if sync_now:
                sync_res = execute_policy_router_sync(policy, triggered_by_id=current_user.id)
                flash(
                    f"Política '{policy.name}' actualizada y sincronizada: {sync_res.response_detail}",
                    "success",
                )
            else:
                flash(f"Política '{policy.name}' actualizada en la base de datos.", "success")
            return redirect(url_for("policies.detail", policy_id=policy.id))
        except ValidationError as exc:
            flash(str(exc), "error")
            return (
                render_template(
                    "policies/form.html",
                    policy=policy,
                    devices=devices,
                    form_data=form_data,
                    policy_Model=AccessPolicy,
                ),
                400,
            )

    return render_template(
        "policies/form.html",
        policy=policy,
        devices=devices,
        form_data=form_data,
        policy_Model=AccessPolicy,
    )


@policies_bp.route("/<int:policy_id>/sync", methods=["POST"])
@login_required
@write_permission_required
def sync_router(policy_id: int):
    policy = db.get_or_404(AccessPolicy, policy_id)
    res = execute_policy_router_sync(policy, triggered_by_id=current_user.id)
    flash(res.response_detail, "info" if not res.is_simulated else "success")
    return redirect(request.referrer or url_for("policies.detail", policy_id=policy.id))


@policies_bp.route("/<int:policy_id>/delete", methods=["POST"])
@login_required
@write_permission_required
def delete(policy_id: int):
    policy = db.get_or_404(AccessPolicy, policy_id)
    name = policy.name
    try:
        delete_policy(policy, user_id=current_user.id)
        flash(f"Política de acceso '{name}' eliminada correctamente.", "info")
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("policies.index"))

