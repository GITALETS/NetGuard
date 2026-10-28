"""
Servicio de gestión de dispositivos (CRUD, validaciones de IP/MAC/Ámbito y auditoría).
"""

from typing import Any, Dict, Optional
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.extensions import db
from app.models.device import Device
from app.services.audit_service import log_audit_event
from app.services.validators import (
    ValidationError,
    validate_and_normalize_ip,
    validate_and_normalize_mac,
    validate_hostname,
    validate_network_scope,
)


def generate_next_internal_code() -> str:
    """Genera un identificador interno único y secuencial para la aplicación (ej. DEV-0001)."""
    last_device = Device.query.order_by(Device.id.desc()).first()
    next_num = (last_device.id + 1) if last_device else 1
    while True:
        candidate = f"DEV-{next_num:04d}"
        exists = Device.query.filter_by(internal_code=candidate).first()
        if not exists:
            return candidate
        next_num += 1


def create_device(
    data: Dict[str, Any],
    user_id: Optional[int] = None,
    is_demo: bool = False,
) -> Device:
    """
    Valida y registra un nuevo dispositivo en la base de datos.
    Importante: El alta en base de datos asigna `router_sync_status='only_in_db'`
    hasta que se ejecute una sincronización explícita con el adaptador.
    """
    name = (data.get("name") or "").strip()
    if not name or len(name) < 2 or len(name) > 100:
        raise ValidationError("El nombre del dispositivo es obligatorio y debe tener entre 2 y 100 caracteres.")

    raw_scope = data.get("network_scope") or "192.168.1.0/24"
    network_scope = validate_network_scope(raw_scope)
    ip_address = validate_and_normalize_ip(data.get("ip_address", ""), network_scope=network_scope)
    mac_address = validate_and_normalize_mac(data.get("mac_address"))
    hostname = validate_hostname(data.get("hostname"))

    device_type = (data.get("device_type") or "other").strip()
    if device_type not in Device.VALID_TYPES:
        raise ValidationError(f"Tipo de dispositivo no válido: '{device_type}'.")

    profile = (data.get("profile") or "family").strip()
    if profile not in Device.VALID_PROFILES:
        profile = "family"

    admin_status = (data.get("admin_status") or "pending").strip()
    if admin_status not in Device.VALID_ADMIN_STATUSES:
        raise ValidationError(f"Estado administrativo no válido: '{admin_status}'.")

    ip_assignment_type = (data.get("ip_assignment_type") or "dhcp_reservation").strip()
    if ip_assignment_type not in Device.VALID_IP_ASSIGNMENTS:
        raise ValidationError(f"Tipo de asignación IP no válido: '{ip_assignment_type}'.")

    # Verificar duplicidad de dirección IP dentro del mismo ámbito de red administrado
    existing_ip = Device.query.filter_by(
        ip_address=ip_address,
        network_scope=network_scope,
    ).first()
    if existing_ip:
        raise ValidationError(
            f"Conflicto de dirección IP: la IP '{ip_address}' ya se encuentra asignada al "
            f"dispositivo '{existing_ip.name}' ({existing_ip.internal_code}) en el ámbito '{network_scope}'."
        )

    # Verificar duplicidad de dirección MAC cuando se proporciona
    if mac_address:
        existing_mac = Device.query.filter_by(mac_address=mac_address).first()
        if existing_mac:
            raise ValidationError(
                f"Conflicto de dirección MAC: la MAC '{mac_address}' ya está registrada en el "
                f"dispositivo '{existing_mac.name}' ({existing_mac.internal_code})."
            )

    internal_code = (data.get("internal_code") or "").strip().upper()
    if internal_code:
        if Device.query.filter_by(internal_code=internal_code).first():
            raise ValidationError(f"El identificador interno '{internal_code}' ya existe.")
    else:
        internal_code = generate_next_internal_code()

    owner_label = (data.get("owner_label") or "").strip() or None
    description = (data.get("description") or "").strip() or None

    device = Device(
        internal_code=internal_code,
        name=name,
        hostname=hostname,
        ip_address=ip_address,
        network_scope=network_scope,
        ip_assignment_type=ip_assignment_type,
        mac_address=mac_address,
        device_type=device_type,
        profile=profile,
        owner_label=owner_label,
        description=description,
        admin_status=admin_status,
        router_sync_status="only_in_db",
        is_demo=bool(is_demo),
        registered_by_id=user_id,
    )

    try:
        db.session.add(device)
        db.session.flush()
        log_audit_event(
            event_type="DEVICE_CREATED",
            module="devices",
            description=(
                f"Alta de dispositivo '{device.name}' ({device.internal_code}) "
                f"con IP {device.ip_address} en ámbito {device.network_scope} "
                f"[Estado: {device.admin_status_label}]."
            ),
            severity="info",
            user_id=user_id,
            target_type="device",
            target_id=device.id,
            metadata={
                "internal_code": device.internal_code,
                "ip_address": device.ip_address,
                "network_scope": device.network_scope,
                "mac_address": device.mac_address,
                "admin_status": device.admin_status,
                "ip_assignment_type": device.ip_assignment_type,
            },
        )
        db.session.commit()
        return device
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError(
            "No fue posible guardar el dispositivo porque la dirección IP, MAC o código interno ya existe."
        ) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        log_audit_event(
            event_type="DEVICE_CREATE_ERROR",
            module="devices",
            description=f"Error de base de datos al intentar registrar dispositivo '{name}'.",
            severity="error",
            user_id=user_id,
            commit=True,
        )
        raise ValidationError("Error interno de base de datos al registrar el dispositivo.") from exc


def update_device(
    device: Device,
    data: Dict[str, Any],
    user_id: Optional[int] = None,
) -> Device:
    """Actualiza los datos de un dispositivo existente validando unicidad y formato."""
    name = (data.get("name") or "").strip()
    if not name or len(name) < 2 or len(name) > 100:
        raise ValidationError("El nombre del dispositivo es obligatorio y debe tener entre 2 y 100 caracteres.")

    raw_scope = data.get("network_scope") or device.network_scope
    network_scope = validate_network_scope(raw_scope)
    ip_address = validate_and_normalize_ip(data.get("ip_address", ""), network_scope=network_scope)
    mac_address = validate_and_normalize_mac(data.get("mac_address"))
    hostname = validate_hostname(data.get("hostname"))

    device_type = (data.get("device_type") or device.device_type).strip()
    if device_type not in Device.VALID_TYPES:
        raise ValidationError(f"Tipo de dispositivo no válido: '{device_type}'.")

    admin_status = (data.get("admin_status") or device.admin_status).strip()
    if admin_status not in Device.VALID_ADMIN_STATUSES:
        raise ValidationError(f"Estado administrativo no válido: '{admin_status}'.")

    ip_assignment_type = (data.get("ip_assignment_type") or device.ip_assignment_type).strip()
    if ip_assignment_type not in Device.VALID_IP_ASSIGNMENTS:
        raise ValidationError(f"Tipo de asignación IP no válido: '{ip_assignment_type}'.")

    # Comprobar si otra entidad ya ocupa la IP en ese mismo ámbito
    existing_ip = Device.query.filter(
        Device.ip_address == ip_address,
        Device.network_scope == network_scope,
        Device.id != device.id,
    ).first()
    if existing_ip:
        raise ValidationError(
            f"Conflicto de dirección IP: la IP '{ip_address}' ya pertenece a "
            f"'{existing_ip.name}' ({existing_ip.internal_code}) en el ámbito '{network_scope}'."
        )

    if mac_address:
        existing_mac = Device.query.filter(
            Device.mac_address == mac_address,
            Device.id != device.id,
        ).first()
        if existing_mac:
            raise ValidationError(
                f"Conflicto de dirección MAC: la MAC '{mac_address}' ya está registrada en "
                f"'{existing_mac.name}' ({existing_mac.internal_code})."
            )

    changes = {}
    if device.name != name:
        changes["name"] = {"from": device.name, "to": name}
    if device.ip_address != ip_address:
        changes["ip_address"] = {"from": device.ip_address, "to": ip_address}
    if device.mac_address != mac_address:
        changes["mac_address"] = {"from": device.mac_address, "to": mac_address}
    if device.admin_status != admin_status:
        changes["admin_status"] = {"from": device.admin_status, "to": admin_status}
    if device.ip_assignment_type != ip_assignment_type:
        changes["ip_assignment_type"] = {"from": device.ip_assignment_type, "to": ip_assignment_type}

    device.name = name
    device.hostname = hostname
    device.ip_address = ip_address
    device.network_scope = network_scope
    device.ip_assignment_type = ip_assignment_type
    device.mac_address = mac_address
    device.device_type = device_type
    profile = (data.get("profile") or getattr(device, "profile", "family") or "family").strip()
    if profile not in Device.VALID_PROFILES:
        profile = "family"
    if getattr(device, "profile", None) != profile:
        changes["profile"] = {"from": getattr(device, "profile", "family"), "to": profile}
    device.profile = profile
    device.owner_label = (data.get("owner_label") or "").strip() or None
    device.description = (data.get("description") or "").strip() or None
    device.admin_status = admin_status

    # Si cambiaron parámetros críticos de red/estado, se marca como pendiente de re-sincronizar
    if any(k in changes for k in ("ip_address", "mac_address", "admin_status", "ip_assignment_type")):
        device.router_sync_status = "only_in_db"

    try:
        event_type = "DEVICE_STATUS_CHANGED" if "admin_status" in changes else "DEVICE_UPDATED"
        log_audit_event(
            event_type=event_type,
            module="devices",
            description=(
                f"Actualización del dispositivo '{device.name}' ({device.internal_code}) "
                f"con IP {device.ip_address}."
            ),
            severity="info",
            user_id=user_id,
            target_type="device",
            target_id=device.id,
            metadata={"changes": changes, "current_ip": device.ip_address},
        )
        db.session.commit()
        return device
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError("Error de integridad: la dirección IP o MAC indicada ya está en uso.") from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al actualizar el dispositivo.") from exc


def delete_device(device: Device, user_id: Optional[int] = None) -> None:
    """Elimina un dispositivo y sus políticas/horarios dependientes registrando el evento en auditoría."""
    code = device.internal_code
    name = device.name
    ip_addr = device.ip_address
    dev_id = device.id

    try:
        db.session.delete(device)
        log_audit_event(
            event_type="DEVICE_DELETED",
            module="devices",
            description=f"Eliminación del dispositivo '{name}' ({code}, IP {ip_addr}) y sus políticas asociadas.",
            severity="warning",
            user_id=user_id,
            target_type="device",
            target_id=dev_id,
            metadata={"internal_code": code, "name": name, "ip_address": ip_addr},
        )
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al intentar eliminar el dispositivo.") from exc

