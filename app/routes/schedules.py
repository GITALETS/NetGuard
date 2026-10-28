"""
Rutas CRUD y Evaluador de Horarios de Acceso (AccessSchedule).
"""

from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.schedule import AccessSchedule
from app.routes.decorators import write_permission_required
from app.services.policy_service import parse_datetime_input
from app.services.schedule_service import (
    create_schedule,
    delete_schedule,
    get_global_upcoming_windows,
    toggle_schedule_active,
    update_schedule,
)
from app.services.validators import ValidationError

schedules_bp = Blueprint("schedules", __name__, url_prefix="/schedules")


@schedules_bp.route("/")
@login_required
def index():
    device_id = request.args.get("device_id", type=int)
    eval_dt_raw = (request.args.get("eval_datetime") or "").strip()

    eval_dt = datetime.now()
    custom_eval_used = False
    if eval_dt_raw:
        try:
            parsed = parse_datetime_input(eval_dt_raw, "Fecha/hora de evaluación")
            if parsed:
                eval_dt = parsed
                custom_eval_used = True
        except ValidationError as exc:
            flash(str(exc), "warning")

    query = AccessSchedule.query
    if device_id:
        query = query.filter(AccessSchedule.device_id == device_id)

    schedules = query.order_by(AccessSchedule.is_active.desc(), AccessSchedule.created_at.desc()).all()
    devices = Device.query.order_by(Device.name.asc()).all()
    upcoming_windows = get_global_upcoming_windows(reference_dt=eval_dt, limit=8)

    return render_template(
        "schedules/index.html",
        schedules=schedules,
        devices=devices,
        device_id=device_id,
        eval_dt=eval_dt,
        eval_dt_str=eval_dt.strftime("%Y-%m-%dT%H:%M"),
        custom_eval_used=custom_eval_used,
        upcoming_windows=upcoming_windows,
        schedule_Model=AccessSchedule,
    )


@schedules_bp.route("/new", methods=["GET", "POST"])
@login_required
@write_permission_required
def create():
    devices = Device.query.order_by(Device.name.asc()).all()
    if not devices:
        flash("Antes de configurar un horario, debe registrar al menos un dispositivo.", "warning")
        return redirect(url_for("devices.create"))

    policies = AccessPolicy.query.order_by(AccessPolicy.name.asc()).all()
    preselected_device_id = request.args.get("device_id", type=int) or devices[0].id

    form_data = {
        "label": "",
        "device_id": preselected_device_id,
        "policy_id": "",
        "days_of_week": ["0", "1", "2", "3", "4"],
        "start_time": "08:00",
        "end_time": "20:00",
        "window_behavior": "allowed_window",
        "is_active": True,
        "enforcement_note": "",
    }

    if request.method == "POST":
        selected_days = request.form.getlist("days_of_week")
        form_data = {
            "label": request.form.get("label", ""),
            "device_id": request.form.get("device_id", ""),
            "policy_id": request.form.get("policy_id", ""),
            "days_of_week": selected_days,
            "start_time": request.form.get("start_time", ""),
            "end_time": request.form.get("end_time", ""),
            "window_behavior": request.form.get("window_behavior", "allowed_window"),
            "is_active": request.form.get("is_active") == "1",
            "enforcement_note": request.form.get("enforcement_note", ""),
        }
        try:
            schedule = create_schedule(form_data, user_id=current_user.id, is_demo=False)
            midnight_msg = (
                " (ventana nocturna que cruza la medianoche hacia el día siguiente)"
                if schedule.crosses_midnight
                else ""
            )
            flash(
                f"Horario '{schedule.label}' configurado correctamente{midnight_msg}.",
                "success",
            )
            return redirect(url_for("schedules.index"))
        except ValidationError as exc:
            flash(str(exc), "error")
            return (
                render_template(
                    "schedules/form.html",
                    schedule=None,
                    devices=devices,
                    policies=policies,
                    form_data=form_data,
                    schedule_Model=AccessSchedule,
                ),
                400,
            )

    return render_template(
        "schedules/form.html",
        schedule=None,
        devices=devices,
        policies=policies,
        form_data=form_data,
        schedule_Model=AccessSchedule,
    )


@schedules_bp.route("/<int:schedule_id>/edit", methods=["GET", "POST"])
@login_required
@write_permission_required
def edit(schedule_id: int):
    schedule = db.get_or_404(AccessSchedule, schedule_id)
    devices = Device.query.order_by(Device.name.asc()).all()
    policies = AccessPolicy.query.order_by(AccessPolicy.name.asc()).all()

    form_data = {
        "label": schedule.label,
        "device_id": schedule.device_id,
        "policy_id": schedule.policy_id or "",
        "days_of_week": [str(d) for d in schedule.days_list_sorted],
        "start_time": schedule.start_time,
        "end_time": schedule.end_time,
        "window_behavior": schedule.window_behavior,
        "is_active": schedule.is_active,
        "enforcement_note": schedule.enforcement_note or "",
    }

    if request.method == "POST":
        selected_days = request.form.getlist("days_of_week")
        form_data = {
            "label": request.form.get("label", ""),
            "device_id": request.form.get("device_id", ""),
            "policy_id": request.form.get("policy_id", ""),
            "days_of_week": selected_days,
            "start_time": request.form.get("start_time", ""),
            "end_time": request.form.get("end_time", ""),
            "window_behavior": request.form.get("window_behavior", "allowed_window"),
            "is_active": request.form.get("is_active") == "1",
            "enforcement_note": request.form.get("enforcement_note", ""),
        }
        try:
            update_schedule(schedule, form_data, user_id=current_user.id)
            flash(f"Horario '{schedule.label}' actualizado correctamente.", "success")
            return redirect(url_for("schedules.index"))
        except ValidationError as exc:
            flash(str(exc), "error")
            return (
                render_template(
                    "schedules/form.html",
                    schedule=schedule,
                    devices=devices,
                    policies=policies,
                    form_data=form_data,
                    schedule_Model=AccessSchedule,
                ),
                400,
            )

    return render_template(
        "schedules/form.html",
        schedule=schedule,
        devices=devices,
        policies=policies,
        form_data=form_data,
        schedule_Model=AccessSchedule,
    )


@schedules_bp.route("/<int:schedule_id>/toggle", methods=["POST"])
@login_required
@write_permission_required
def toggle(schedule_id: int):
    schedule = db.get_or_404(AccessSchedule, schedule_id)
    try:
        toggle_schedule_active(schedule, user_id=current_user.id)
        status_word = "activado" if schedule.is_active else "desactivado"
        flash(f"El horario '{schedule.label}' ha sido {status_word}.", "info")
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("schedules.index"))


@schedules_bp.route("/<int:schedule_id>/delete", methods=["POST"])
@login_required
@write_permission_required
def delete(schedule_id: int):
    schedule = db.get_or_404(AccessSchedule, schedule_id)
    label = schedule.label
    try:
        delete_schedule(schedule, user_id=current_user.id)
        flash(f"Horario '{label}' eliminado correctamente.", "info")
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("schedules.index"))

