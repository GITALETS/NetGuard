"""
Servicio de inicialización de datos de demostración para el Modo Laboratorio.
Todos los registros generados se identifican explícitamente con `is_demo=True`.
"""

from datetime import timedelta
from typing import Dict, Optional
from app.extensions import db
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.schedule import AccessSchedule
from app.models.user import utc_now_naive
from app.services.audit_service import log_audit_event
from app.services.device_service import create_device
from app.services.policy_service import create_policy
from app.services.router_adapter import execute_device_router_sync, execute_policy_router_sync
from app.services.schedule_service import create_schedule


def seed_laboratory_demo_data(user_id: Optional[int] = None) -> Dict[str, int]:
    """
    Carga un conjunto coherente de dispositivos, políticas y horarios simulados
    claramente identificados como datos de laboratorio (`is_demo=True`).
    Es idempotente: no duplica dispositivos si ya fueron cargados.
    """
    now = utc_now_naive()
    created_counts = {"devices": 0, "policies": 0, "schedules": 0}

    demo_devices_spec = [
        {
            "internal_code": "DEV-0101",
            "name": "Estación Principal Estudio [DEMO]",
            "hostname": "pc-estudio-tesis.lan",
            "ip_address": "192.168.1.10",
            "network_scope": "192.168.1.0/24",
            "ip_assignment_type": "dhcp_reservation",
            "mac_address": "AA:BB:CC:11:22:01",
            "device_type": "workstation",
            "owner_label": "Administrador del Hogar (Datos Demo)",
            "description": "Equipo de escritorio con reserva DHCP vinculada por MAC en entorno de laboratorio.",
            "admin_status": "authorized",
            "sync_in_lab": True,
        },
        {
            "internal_code": "DEV-0102",
            "name": "Laptop Estudio Universitario [DEMO]",
            "hostname": "laptop-ing-sistemas.lan",
            "ip_address": "192.168.1.25",
            "network_scope": "192.168.1.0/24",
            "ip_assignment_type": "dhcp_reservation",
            "mac_address": "AA:BB:CC:11:22:02",
            "device_type": "laptop",
            "owner_label": "Estudiante (Datos Demo)",
            "description": "Portátil autorizada con horario académico prioritario.",
            "admin_status": "authorized",
            "sync_in_lab": True,
        },
        {
            "internal_code": "DEV-0103",
            "name": "Tableta Infantil Sala [DEMO]",
            "hostname": "tablet-sala-familiar.lan",
            "ip_address": "192.168.1.40",
            "network_scope": "192.168.1.0/24",
            "ip_assignment_type": "dhcp_reservation",
            "mac_address": "AA:BB:CC:11:22:03",
            "device_type": "tablet",
            "owner_label": "Familiar Menor (Datos Demo)",
            "description": "Dispositivo con control parental de horarios y restricción nocturna.",
            "admin_status": "restricted",
            "sync_in_lab": True,
        },
        {
            "internal_code": "DEV-0104",
            "name": "Smart TV Sala Principal [DEMO]",
            "hostname": "smarttv-sala.lan",
            "ip_address": "192.168.1.60",
            "network_scope": "192.168.1.0/24",
            "ip_assignment_type": "static_manual",
            "mac_address": "AA:BB:CC:11:22:04",
            "device_type": "smart_tv",
            "owner_label": "Área Común (Datos Demo)",
            "description": "Televisor con IP fija manual y ventana permitida vespertina/nocturna.",
            "admin_status": "restricted",
            "sync_in_lab": False,
        },
        {
            "internal_code": "DEV-0105",
            "name": "Cámara IoT Exterior [DEMO]",
            "hostname": "cam-iot-patio.lan",
            "ip_address": "192.168.1.120",
            "network_scope": "192.168.1.0/24",
            "ip_assignment_type": "dhcp_dynamic_observed",
            "mac_address": "AA:BB:CC:11:22:05",
            "device_type": "iot",
            "owner_label": "Seguridad Domótica (Datos Demo)",
            "description": "Dispositivo IoT con concesión DHCP dinámica y bloqueo hacia Internet exterior.",
            "admin_status": "blocked",
            "sync_in_lab": True,
        },
        {
            "internal_code": "DEV-0106",
            "name": "Smartphone Invitado Temporal [DEMO]",
            "hostname": "android-visita.lan",
            "ip_address": "192.168.1.185",
            "network_scope": "192.168.1.0/24",
            "ip_assignment_type": "dhcp_dynamic_observed",
            "mac_address": None,
            "device_type": "smartphone",
            "owner_label": "Visita Temporal (Datos Demo)",
            "description": "Dispositivo observado por IP dinámica sin dirección MAC fija confirmada.",
            "admin_status": "pending",
            "sync_in_lab": False,
        },
    ]

    devices_by_code = {}
    for spec in demo_devices_spec:
        existing = Device.query.filter_by(internal_code=spec["internal_code"]).first()
        if existing:
            devices_by_code[spec["internal_code"]] = existing
            continue
        existing_ip = Device.query.filter_by(
            ip_address=spec["ip_address"],
            network_scope=spec["network_scope"],
        ).first()
        if existing_ip:
            devices_by_code[spec["internal_code"]] = existing_ip
            continue

        dev = create_device(spec, user_id=user_id, is_demo=True)
        if spec.get("sync_in_lab"):
            execute_device_router_sync(dev, triggered_by_id=user_id, commit=True)
        devices_by_code[spec["internal_code"]] = dev
        created_counts["devices"] += 1

    # Crear políticas representativas de las 5 categorías requeridas
    dev_pc = devices_by_code.get("DEV-0101")
    dev_laptop = devices_by_code.get("DEV-0102")
    dev_tablet = devices_by_code.get("DEV-0103")
    dev_iot = devices_by_code.get("DEV-0105")
    dev_guest = devices_by_code.get("DEV-0106")

    demo_policies_spec = []
    if dev_pc:
        demo_policies_spec.append(
            {
                "name": "Acceso Permanente Estación Principal [DEMO]",
                "description": "Política permanente sin vencimiento para el equipo de administración.",
                "device_id": dev_pc.id,
                "policy_type": "permanent_access",
                "action": "allow",
                "priority": 10,
                "status": "active",
                "valid_from": now - timedelta(days=15),
                "valid_until": None,
                "observations": "Dato de demostración de laboratorio: acceso irrestricto LAN/WAN.",
                "sync": True,
            }
        )
    if dev_laptop:
        demo_policies_spec.append(
            {
                "name": "Autorización Administrativa Laptop Tesis [DEMO]",
                "description": "Autorización formal para equipo portátil de desarrollo.",
                "device_id": dev_laptop.id,
                "policy_type": "administrative_auth",
                "action": "allow",
                "priority": 20,
                "status": "active",
                "valid_from": now - timedelta(days=7),
                "valid_until": now + timedelta(days=90),
                "observations": "Validada con reserva DHCP por MAC.",
                "sync": True,
            }
        )
    if dev_tablet:
        demo_policies_spec.append(
            {
                "name": "Filtro de Navegación Familiar y Puertos Seguros [DEMO]",
                "description": "Restricción configurable de categorías DNS y bloqueo de puertos no estándar.",
                "device_id": dev_tablet.id,
                "policy_type": "navigation_restriction",
                "action": "restrict",
                "priority": 30,
                "status": "active",
                "valid_from": now - timedelta(days=5),
                "valid_until": now + timedelta(days=60),
                "navigation_profile": "DNS-SafeSearch; Bloqueo Adultos/Apuestas; Solo TCP 80,443",
                "observations": "Política configurada en BD y simulada en adaptador de laboratorio.",
                "sync": True,
            }
        )
        demo_policies_spec.append(
            {
                "name": "Política de Horario de Estudio Tableta [DEMO]",
                "description": "Permite conexión únicamente en las ventanas horarias autorizadas.",
                "device_id": dev_tablet.id,
                "policy_type": "allowed_schedule",
                "action": "allow",
                "priority": 40,
                "status": "active",
                "valid_from": now - timedelta(days=5),
                "valid_until": now + timedelta(days=60),
                "observations": "Vinculada a programación horaria vespertina.",
                "sync": False,
            }
        )
    if dev_iot:
        demo_policies_spec.append(
            {
                "name": "Aislamiento WAN Cámara IoT [DEMO]",
                "description": "Bloquea salida hacia Internet permitiendo solo administración local.",
                "device_id": dev_iot.id,
                "policy_type": "administrative_auth",
                "action": "block",
                "priority": 15,
                "status": "active",
                "valid_from": now - timedelta(days=10),
                "valid_until": None,
                "observations": "Mitigación defensiva para dispositivo IoT con firmware cerrado.",
                "sync": True,
            }
        )
    if dev_guest:
        demo_policies_spec.append(
            {
                "name": "Acceso Temporal Invitado Fin de Semana (Vencida) [DEMO]",
                "description": "Ejemplo de política temporal cuyo intervalo de vigencia ya expiró.",
                "device_id": dev_guest.id,
                "policy_type": "temporary_access",
                "action": "allow",
                "priority": 60,
                "status": "active",
                "valid_from": now - timedelta(days=4),
                "valid_until": now - timedelta(days=1),
                "observations": "Demuestra que una política vencida se evalúa automáticamente como Expirada.",
                "sync": False,
            }
        )

    schedule_policy_ref = None
    for p_spec in demo_policies_spec:
        existing_pol = AccessPolicy.query.filter_by(
            name=p_spec["name"],
            device_id=p_spec["device_id"],
        ).first()
        if existing_pol:
            if p_spec["policy_type"] == "allowed_schedule":
                schedule_policy_ref = existing_pol
            continue

        should_sync = p_spec.pop("sync", False)
        pol = create_policy(p_spec, user_id=user_id, is_demo=True)
        if should_sync:
            execute_policy_router_sync(pol, triggered_by_id=user_id, commit=True)
        if pol.policy_type == "allowed_schedule":
            schedule_policy_ref = pol
        created_counts["policies"] += 1

    # Crear horarios demostrativos (incluyendo uno diurno y uno que cruza la medianoche)
    demo_schedules_spec = []
    if dev_tablet:
        demo_schedules_spec.append(
            {
                "label": "Ventana Vespertina Tableta (Lun–Vie) [DEMO]",
                "device_id": dev_tablet.id,
                "policy_id": schedule_policy_ref.id if schedule_policy_ref else None,
                "days_of_week": [0, 1, 2, 3, 4],
                "start_time": "16:00",
                "end_time": "20:30",
                "window_behavior": "allowed_window",
                "is_active": True,
                "enforcement_note": "Horario permitido después de clases de lunes a viernes.",
            }
        )
        demo_schedules_spec.append(
            {
                "label": "Restricción Nocturna Descanso (Cruza Medianoche) [DEMO]",
                "device_id": dev_tablet.id,
                "policy_id": None,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "start_time": "22:00",
                "end_time": "06:30",
                "window_behavior": "restricted_window",
                "is_active": True,
                "enforcement_note": "Inicia a las 22:00 y finaliza a las 06:30 de la mañana siguiente.",
            }
        )
    if dev_laptop:
        demo_schedules_spec.append(
            {
                "label": "Jornada Académica y Laboratorio [DEMO]",
                "device_id": dev_laptop.id,
                "policy_id": None,
                "days_of_week": [0, 1, 2, 3, 4, 5],
                "start_time": "07:00",
                "end_time": "23:00",
                "window_behavior": "allowed_window",
                "is_active": True,
                "enforcement_note": "Ventana amplia para prácticas de laboratorio universitario.",
            }
        )

    for s_spec in demo_schedules_spec:
        existing_sch = AccessSchedule.query.filter_by(
            label=s_spec["label"],
            device_id=s_spec["device_id"],
        ).first()
        if existing_sch:
            continue
        create_schedule(s_spec, user_id=user_id, is_demo=True)
        created_counts["schedules"] += 1

    log_audit_event(
        event_type="DEMO_DATA_SEEDED",
        module="system",
        description=(
            f"Carga de escenario demostrativo de laboratorio completada: "
            f"{created_counts['devices']} dispositivos, {created_counts['policies']} políticas y "
            f"{created_counts['schedules']} horarios."
        ),
        severity="info",
        user_id=user_id,
        metadata=created_counts,
        commit=True,
    )
    return created_counts


def clear_laboratory_demo_data(user_id: Optional[int] = None) -> Dict[str, int]:
    """Elimina únicamente los registros identificados como datos de demostración (`is_demo=True`)."""
    demo_schedules = AccessSchedule.query.filter_by(is_demo=True).all()
    demo_policies = AccessPolicy.query.filter_by(is_demo=True).all()
    demo_devices = Device.query.filter_by(is_demo=True).all()

    counts = {
        "schedules": len(demo_schedules),
        "policies": len(demo_policies),
        "devices": len(demo_devices),
    }

    for sch in demo_schedules:
        db.session.delete(sch)
    for pol in demo_policies:
        db.session.delete(pol)
    for dev in demo_devices:
        db.session.delete(dev)

    log_audit_event(
        event_type="DEMO_DATA_CLEARED",
        module="system",
        description=(
            f"Limpieza de datos de demostración de laboratorio: "
            f"{counts['devices']} dispositivos, {counts['policies']} políticas y {counts['schedules']} horarios eliminados."
        ),
        severity="warning",
        user_id=user_id,
        metadata=counts,
        commit=True,
    )
    return counts

