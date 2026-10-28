"""
Servicio de gestión y evaluación de Horarios de Acceso (AccessSchedule).
Incluye soporte para horarios que cruzan la medianoche y cálculo de próximas
ventanas de acceso programadas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.schedule import AccessSchedule
from app.services.audit_service import log_audit_event
from app.services.validators import ValidationError, validate_schedule_params


def create_schedule(
    data: Dict[str, Any],
    user_id: Optional[int] = None,
    is_demo: bool = False,
) -> AccessSchedule:
    """Crea una programación horaria validando días, horas, cruce de medianoche y relaciones."""
    label = (data.get("label") or "").strip()
    if not label or len(label) < 3 or len(label) > 120:
        raise ValidationError("El nombre o etiqueta del horario es obligatorio (entre 3 y 120 caracteres).")

    try:
        device_id = int(data.get("device_id"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Debe seleccionar un dispositivo válido para el horario.") from exc

    device = db.session.get(Device, device_id)
    if not device:
        raise ValidationError("El dispositivo seleccionado no existe.")

    policy_id = None
    raw_policy_id = data.get("policy_id")
    if raw_policy_id not in (None, "", "0", 0):
        try:
            policy_id = int(raw_policy_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Identificador de política inválido.") from exc
        policy = db.session.get(AccessPolicy, policy_id)
        if not policy:
            raise ValidationError("La política asociada seleccionada no existe.")
        if policy.device_id != device.id:
            raise ValidationError(
                "Inconsistencia relacional: la política seleccionada pertenece a otro dispositivo."
            )

    days_input = data.get("days_of_week")
    if isinstance(days_input, str):
        days_input = [d.strip() for d in days_input.split(",") if d.strip()]

    window_behavior = (data.get("window_behavior") or "allowed_window").strip()
    days_csv, start_clean, end_clean, crosses_midnight = validate_schedule_params(
        days_input=days_input,
        start_time_str=data.get("start_time", ""),
        end_time_str=data.get("end_time", ""),
        window_behavior=window_behavior,
    )

    is_active = bool(data.get("is_active", True))
    enforcement_note = (data.get("enforcement_note") or "").strip() or None

    schedule = AccessSchedule(
        label=label,
        device_id=device.id,
        policy_id=policy_id,
        days_of_week=days_csv,
        start_time=start_clean,
        end_time=end_clean,
        window_behavior=window_behavior,
        crosses_midnight=crosses_midnight,
        is_active=is_active,
        enforcement_note=enforcement_note,
        is_demo=bool(is_demo),
        created_by_id=user_id,
    )

    try:
        db.session.add(schedule)
        db.session.flush()
        midnight_tag = " (Cruza medianoche)" if crosses_midnight else ""
        log_audit_event(
            event_type="SCHEDULE_CREATED",
            module="schedules",
            description=(
                f"Creación de horario '{schedule.label}' ({start_clean} a {end_clean}{midnight_tag}) "
                f"para dispositivo {device.internal_code} ({device.ip_address})."
            ),
            severity="info",
            user_id=user_id,
            target_type="schedule",
            target_id=schedule.id,
            metadata={
                "device_id": device.id,
                "policy_id": policy_id,
                "days_of_week": days_csv,
                "start_time": start_clean,
                "end_time": end_clean,
                "crosses_midnight": crosses_midnight,
                "is_active": is_active,
            },
        )
        db.session.commit()
        return schedule
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al guardar el horario de acceso.") from exc


def update_schedule(
    schedule: AccessSchedule,
    data: Dict[str, Any],
    user_id: Optional[int] = None,
) -> AccessSchedule:
    """Actualiza los parámetros de un horario programado."""
    label = (data.get("label") or "").strip()
    if not label or len(label) < 3 or len(label) > 120:
        raise ValidationError("El nombre o etiqueta del horario es obligatorio (entre 3 y 120 caracteres).")

    device_id = int(data.get("device_id", schedule.device_id))
    device = db.session.get(Device, device_id)
    if not device:
        raise ValidationError("El dispositivo seleccionado no existe.")

    policy_id = None
    raw_policy_id = data.get("policy_id")
    if raw_policy_id not in (None, "", "0", 0):
        policy_id = int(raw_policy_id)
        policy = db.session.get(AccessPolicy, policy_id)
        if not policy or policy.device_id != device.id:
            raise ValidationError("La política seleccionada no es válida para el dispositivo indicado.")

    days_input = data.get("days_of_week")
    if isinstance(days_input, str):
        days_input = [d.strip() for d in days_input.split(",") if d.strip()]

    window_behavior = (data.get("window_behavior") or schedule.window_behavior).strip()
    days_csv, start_clean, end_clean, crosses_midnight = validate_schedule_params(
        days_input=days_input,
        start_time_str=data.get("start_time", schedule.start_time),
        end_time_str=data.get("end_time", schedule.end_time),
        window_behavior=window_behavior,
    )

    schedule.label = label
    schedule.device_id = device.id
    schedule.policy_id = policy_id
    schedule.days_of_week = days_csv
    schedule.start_time = start_clean
    schedule.end_time = end_clean
    schedule.window_behavior = window_behavior
    schedule.crosses_midnight = crosses_midnight
    if "is_active" in data:
        schedule.is_active = bool(data.get("is_active"))
    schedule.enforcement_note = (data.get("enforcement_note") or "").strip() or None

    try:
        log_audit_event(
            event_type="SCHEDULE_UPDATED",
            module="schedules",
            description=(
                f"Actualización de horario '{schedule.label}' (ID #{schedule.id}) "
                f"para dispositivo {device.internal_code}."
            ),
            severity="info",
            user_id=user_id,
            target_type="schedule",
            target_id=schedule.id,
            metadata={
                "start_time": start_clean,
                "end_time": end_clean,
                "crosses_midnight": crosses_midnight,
                "is_active": schedule.is_active,
            },
        )
        db.session.commit()
        return schedule
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al actualizar el horario.") from exc


def toggle_schedule_active(
    schedule: AccessSchedule,
    user_id: Optional[int] = None,
) -> AccessSchedule:
    """Activa o desactiva rápidamente una programación horaria."""
    schedule.is_active = not schedule.is_active
    state_txt = "Activado" if schedule.is_active else "Desactivado"
    try:
        log_audit_event(
            event_type="SCHEDULE_TOGGLED",
            module="schedules",
            description=f"Horario '{schedule.label}' (ID #{schedule.id}) cambiado a estado: {state_txt}.",
            severity="info",
            user_id=user_id,
            target_type="schedule",
            target_id=schedule.id,
            metadata={"is_active": schedule.is_active},
        )
        db.session.commit()
        return schedule
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al cambiar el estado del horario.") from exc


def delete_schedule(schedule: AccessSchedule, user_id: Optional[int] = None) -> None:
    """Elimina un horario programado y registra la operación en auditoría."""
    sch_id = schedule.id
    sch_label = schedule.label
    dev_code = schedule.device.internal_code if schedule.device else "N/A"
    try:
        db.session.delete(schedule)
        log_audit_event(
            event_type="SCHEDULE_DELETED",
            module="schedules",
            description=f"Eliminación de horario '{sch_label}' (ID #{sch_id}, Dispositivo {dev_code}).",
            severity="warning",
            user_id=user_id,
            target_type="schedule",
            target_id=sch_id,
            metadata={"label": sch_label, "device_code": dev_code},
        )
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al eliminar el horario.") from exc


def get_global_upcoming_windows(
    reference_dt: Optional[datetime] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """
    Reúne las próximas ventanas horarias de todos los horarios activos, ordenadas
    cronológicamente, indicando si se encuentran actualmente en curso.
    """
    now = reference_dt or datetime.now()
    active_schedules = AccessSchedule.query.filter_by(is_active=True).all()
    items: List[Dict[str, Any]] = []

    for sch in active_schedules:
        windows = sch.get_upcoming_windows(reference_dt=now, max_windows=2)
        for win_start, win_end in windows:
            is_ongoing = win_start <= now < win_end
            items.append(
                {
                    "schedule": sch,
                    "device": sch.device,
                    "policy": sch.policy,
                    "window_start": win_start,
                    "window_end": win_end,
                    "is_ongoing": is_ongoing,
                    "crosses_midnight": sch.crosses_midnight,
                    "behavior": sch.window_behavior,
                    "behavior_label": sch.behavior_label,
                }
            )

    items.sort(key=lambda x: (not x["is_ongoing"], x["window_start"]))
    return items[:limit]

