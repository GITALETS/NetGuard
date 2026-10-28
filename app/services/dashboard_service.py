"""
Servicio de agregación de métricas en tiempo real para el Dashboard.
Todas las cifras se consultan directamente de la base de datos relacional.
"""

from datetime import datetime
from typing import Any, Dict
from app.models.audit import AuditLog
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.schedule import AccessSchedule
from app.models.user import utc_now_naive
from app.services.policy_service import refresh_expired_policies
from app.services.router_adapter import get_router_adapter
from app.services.schedule_service import get_global_upcoming_windows


def get_dashboard_metrics(reference_time: datetime | None = None) -> Dict[str, Any]:
    """Calcula todas las métricas e indicadores del panel principal desde la base de datos."""
    now_utc = reference_time or utc_now_naive()
    refresh_expired_policies(now_utc)

    all_devices = Device.query.order_by(Device.created_at.desc()).all()
    total_devices = len(all_devices)
    demo_devices_count = sum(1 for d in all_devices if d.is_demo)

    status_counts = {
        "authorized": 0,
        "restricted": 0,
        "blocked": 0,
        "pending": 0,
    }
    sync_counts = {
        "only_in_db": 0,
        "simulated_applied": 0,
        "applied_confirmed": 0,
        "not_supported": 0,
        "sync_error": 0,
    }

    for dev in all_devices:
        status_counts[dev.admin_status] = status_counts.get(dev.admin_status, 0) + 1
        sync_counts[dev.router_sync_status] = sync_counts.get(dev.router_sync_status, 0) + 1

    # Dispositivos bloqueados o no autorizados (blocked + pending + restricted desglosado)
    blocked_or_unauthorized = status_counts["blocked"] + status_counts["pending"]

    all_policies = AccessPolicy.query.order_by(AccessPolicy.priority.asc()).all()
    active_policies = [p for p in all_policies if p.is_currently_effective(now_utc)]
    expired_policies = [p for p in all_policies if p.effective_status_at(now_utc) == "expired"]
    scheduled_policies = [p for p in all_policies if p.effective_status_at(now_utc) == "scheduled"]

    enforcement_counts = {
        "stored_in_db": sum(1 for p in active_policies if p.enforcement_status == "stored_in_db"),
        "simulated_in_lab": sum(1 for p in active_policies if p.enforcement_status == "simulated_in_lab"),
        "applied_in_router": sum(1 for p in active_policies if p.enforcement_status == "applied_in_router"),
    }

    # Distribución porcentual de dispositivos por estado (calculada sobre total real en BD)
    distribution = []
    status_meta = [
        ("authorized", "Autorizados", "emerald"),
        ("restricted", "Restringidos", "amber"),
        ("blocked", "Bloqueados", "rose"),
        ("pending", "Pendientes de Autorización", "slate"),
    ]
    for key, label, color in status_meta:
        cnt = status_counts.get(key, 0)
        pct = round((cnt / total_devices) * 100, 1) if total_devices > 0 else 0.0
        distribution.append(
            {
                "key": key,
                "label": label,
                "count": cnt,
                "percentage": pct,
                "color": color,
            }
        )

    upcoming_windows = get_global_upcoming_windows(limit=6)
    active_schedules_count = AccessSchedule.query.filter_by(is_active=True).count()
    recent_audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()
    adapter_info = get_router_adapter().get_diagnostics()

    return {
        "total_devices": total_devices,
        "demo_devices_count": demo_devices_count,
        "has_demo_data": demo_devices_count > 0,
        "authorized_devices": status_counts["authorized"],
        "restricted_devices": status_counts["restricted"],
        "blocked_devices": status_counts["blocked"],
        "pending_devices": status_counts["pending"],
        "blocked_or_unauthorized": blocked_or_unauthorized,
        "status_counts": status_counts,
        "sync_counts": sync_counts,
        "distribution": distribution,
        "total_policies": len(all_policies),
        "active_policies_count": len(active_policies),
        "expired_policies_count": len(expired_policies),
        "scheduled_policies_count": len(scheduled_policies),
        "enforcement_counts": enforcement_counts,
        "active_schedules_count": active_schedules_count,
        "upcoming_windows": upcoming_windows,
        "recent_audit_logs": recent_audit_logs,
        "recent_devices": all_devices[:5],
        "adapter_info": adapter_info,
    }

