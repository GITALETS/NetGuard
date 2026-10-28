"""
Servicio de gestión de Políticas de Acceso.
Incluye validación de intervalos temporales, detección de contradicciones,
cálculo de vigencia/expiración y separación entre registro en BD y aplicación en red.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.user import utc_now_naive
from app.services.audit_service import log_audit_event
from app.services.validators import ValidationError, validate_policy_temporal_rules


def parse_datetime_input(value: Any, field_label: str, required: bool = False) -> Optional[datetime]:
    """Convierte un objeto datetime o cadena ISO ('YYYY-MM-DDTHH:MM' / 'YYYY-MM-DD HH:MM') a datetime."""
    if value is None or value == "":
        if required:
            raise ValidationError(f"El campo '{field_label}' es obligatorio.")
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    raw = str(value).strip()
    if not raw:
        if required:
            raise ValidationError(f"El campo '{field_label}' es obligatorio.")
        return None

    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValidationError(
        f"Formato de fecha/hora inválido en '{field_label}': '{raw}'. Use AAAA-MM-DD HH:MM."
    )


def intervals_overlap(
    start_a: datetime,
    end_a: Optional[datetime],
    start_b: datetime,
    end_b: Optional[datetime],
) -> bool:
    """Determina si dos intervalos temporales [start, end) se solapan (end=None representa infinito)."""
    max_start = max(start_a, start_b)
    if end_a is None and end_b is None:
        return True
    if end_a is None:
        return max_start < end_b
    if end_b is None:
        return max_start < end_a
    min_end = min(end_a, end_b)
    return max_start < min_end


def check_contradictory_policies(
    device_id: int,
    action: str,
    priority: int,
    valid_from: datetime,
    valid_until: Optional[datetime],
    exclude_policy_id: Optional[int] = None,
) -> None:
    """
    Evita combinaciones contradictorias activas sobre el mismo dispositivo:
    No permite dos políticas activas solapadas en el tiempo con la misma prioridad
    y acciones opuestas (ej. 'allow' frente a 'block' o 'restrict').
    """
    query = AccessPolicy.query.filter(
        AccessPolicy.device_id == device_id,
        AccessPolicy.status == "active",
    )
    if exclude_policy_id is not None:
        query = query.filter(AccessPolicy.id != exclude_policy_id)

    now = utc_now_naive()
    for existing in query.all():
        if existing.is_expired_at(now):
            continue
        if existing.priority == priority and existing.action != action:
            if intervals_overlap(valid_from, valid_until, existing.valid_from, existing.valid_until):
                raise ValidationError(
                    f"Combinación contradictoria detectada: el dispositivo ya tiene la política activa "
                    f"'{existing.name}' con la misma prioridad ({priority}) y acción opuesta "
                    f"('{existing.action_label}') en un intervalo temporal solapado. "
                    "Modifique la prioridad o desactive la política existente."
                )


def refresh_expired_policies(reference_time: Optional[datetime] = None) -> int:
    """
    Actualiza a estado 'expired' aquellas políticas marcadas como 'active' cuya
    fecha de finalización ya haya transcurrido. Devuelve el número de registros actualizados.
    """
    now = reference_time or utc_now_naive()
    expired_candidates = AccessPolicy.query.filter(
        AccessPolicy.status == "active",
        AccessPolicy.valid_until.isnot(None),
        AccessPolicy.valid_until <= now,
    ).all()

    count = 0
    for pol in expired_candidates:
        pol.status = "expired"
        pol.last_evaluated_at = now
        count += 1

    if count > 0:
        db.session.commit()
    return count


def create_policy(
    data: Dict[str, Any],
    user_id: Optional[int] = None,
    is_demo: bool = False,
) -> AccessPolicy:
    """Crea una nueva política de acceso validando reglas temporales y contradicciones."""
    name = (data.get("name") or "").strip()
    if not name or len(name) < 3 or len(name) > 120:
        raise ValidationError("El nombre de la política es obligatorio (entre 3 y 120 caracteres).")

    try:
        device_id = int(data.get("device_id"))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Debe seleccionar un dispositivo válido para asociar la política.") from exc

    device = db.session.get(Device, device_id)
    if not device:
        raise ValidationError("El dispositivo seleccionado no existe.")

    policy_type = (data.get("policy_type") or "").strip()
    action = (data.get("action") or "allow").strip()
    navigation_profile = (data.get("navigation_profile") or "").strip() or None

    valid_from = parse_datetime_input(data.get("valid_from"), "Fecha de inicio", required=True)
    valid_until = parse_datetime_input(data.get("valid_until"), "Fecha de finalización", required=False)

    validate_policy_temporal_rules(
        policy_type=policy_type,
        action=action,
        valid_from=valid_from,
        valid_until=valid_until,
        navigation_profile=navigation_profile,
    )

    try:
        priority = int(data.get("priority", 50))
        if not (1 <= priority <= 100):
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValidationError("La prioridad debe ser un número entero entre 1 (máxima) y 100 (mínima).") from exc

    status = (data.get("status") or "active").strip()
    if status not in AccessPolicy.VALID_STATUSES:
        raise ValidationError(f"Estado de política inválido: '{status}'.")

    # Si se crea con una fecha final ya vencida, su estado efectivo pasa a 'expired'
    now = utc_now_naive()
    if valid_until is not None and valid_until <= now:
        status = "expired"

    if status == "active":
        check_contradictory_policies(
            device_id=device.id,
            action=action,
            priority=priority,
            valid_from=valid_from,
            valid_until=valid_until,
        )

    policy = AccessPolicy(
        name=name,
        description=(data.get("description") or "").strip() or None,
        device_id=device.id,
        policy_type=policy_type,
        action=action,
        priority=priority,
        status=status,
        valid_from=valid_from,
        valid_until=valid_until,
        navigation_profile=navigation_profile,
        observations=(data.get("observations") or "").strip() or None,
        enforcement_status="stored_in_db",
        last_evaluated_at=now,
        is_demo=bool(is_demo),
        created_by_id=user_id,
    )

    try:
        db.session.add(policy)
        db.session.flush()
        log_audit_event(
            event_type="POLICY_CREATED",
            module="policies",
            description=(
                f"Creación de política '{policy.name}' ({policy.policy_type_label}) "
                f"para dispositivo {device.internal_code} ({device.ip_address}) "
                f"[Acción: {policy.action_label}, Estado BD: {policy.effective_status_label}]."
            ),
            severity="info",
            user_id=user_id,
            target_type="policy",
            target_id=policy.id,
            metadata={
                "device_id": device.id,
                "device_ip": device.ip_address,
                "policy_type": policy.policy_type,
                "action": policy.action,
                "priority": policy.priority,
                "status": policy.status,
                "enforcement_status": policy.enforcement_status,
            },
        )
        db.session.commit()
        return policy
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al registrar la política de acceso.") from exc


def update_policy(
    policy: AccessPolicy,
    data: Dict[str, Any],
    user_id: Optional[int] = None,
) -> AccessPolicy:
    """Actualiza una política de acceso existente validando sus restricciones."""
    name = (data.get("name") or "").strip()
    if not name or len(name) < 3 or len(name) > 120:
        raise ValidationError("El nombre de la política es obligatorio (entre 3 y 120 caracteres).")

    device_id = int(data.get("device_id", policy.device_id))
    device = db.session.get(Device, device_id)
    if not device:
        raise ValidationError("El dispositivo seleccionado no existe.")

    policy_type = (data.get("policy_type") or policy.policy_type).strip()
    action = (data.get("action") or policy.action).strip()
    navigation_profile = (data.get("navigation_profile") or "").strip() or None

    valid_from = parse_datetime_input(data.get("valid_from", policy.valid_from), "Fecha de inicio", required=True)
    valid_until = parse_datetime_input(data.get("valid_until"), "Fecha de finalización", required=False)

    validate_policy_temporal_rules(
        policy_type=policy_type,
        action=action,
        valid_from=valid_from,
        valid_until=valid_until,
        navigation_profile=navigation_profile,
    )

    try:
        priority = int(data.get("priority", policy.priority))
        if not (1 <= priority <= 100):
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValidationError("La prioridad debe ser un número entero entre 1 y 100.") from exc

    status = (data.get("status") or policy.status).strip()
    if status not in AccessPolicy.VALID_STATUSES:
        raise ValidationError(f"Estado de política inválido: '{status}'.")

    now = utc_now_naive()
    if valid_until is not None and valid_until <= now and status == "active":
        status = "expired"

    if status == "active":
        check_contradictory_policies(
            device_id=device.id,
            action=action,
            priority=priority,
            valid_from=valid_from,
            valid_until=valid_until,
            exclude_policy_id=policy.id,
        )

    old_status = policy.status
    policy.name = name
    policy.description = (data.get("description") or "").strip() or None
    policy.device_id = device.id
    policy.policy_type = policy_type
    policy.action = action
    policy.priority = priority
    policy.status = status
    policy.valid_from = valid_from
    policy.valid_until = valid_until
    policy.navigation_profile = navigation_profile
    policy.observations = (data.get("observations") or "").strip() or None
    policy.enforcement_status = "stored_in_db"
    policy.last_evaluated_at = now

    try:
        evt = "POLICY_STATUS_CHANGED" if old_status != status else "POLICY_UPDATED"
        log_audit_event(
            event_type=evt,
            module="policies",
            description=(
                f"Modificación de política '{policy.name}' (ID #{policy.id}) "
                f"para dispositivo {device.internal_code} [Estado efectivo: {policy.effective_status_label}]."
            ),
            severity="info",
            user_id=user_id,
            target_type="policy",
            target_id=policy.id,
            metadata={
                "old_status": old_status,
                "new_status": status,
                "effective_status": policy.effective_status,
                "action": policy.action,
            },
        )
        db.session.commit()
        return policy
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al actualizar la política.") from exc


def delete_policy(policy: AccessPolicy, user_id: Optional[int] = None) -> None:
    """Elimina una política de acceso y registra la operación en el historial."""
    pol_id = policy.id
    pol_name = policy.name
    dev_code = policy.device.internal_code if policy.device else "N/A"

    try:
        db.session.delete(policy)
        log_audit_event(
            event_type="POLICY_DELETED",
            module="policies",
            description=f"Eliminación de política '{pol_name}' (ID #{pol_id}, Dispositivo {dev_code}).",
            severity="warning",
            user_id=user_id,
            target_type="policy",
            target_id=pol_id,
            metadata={"policy_name": pol_name, "device_code": dev_code},
        )
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al eliminar la política.") from exc

