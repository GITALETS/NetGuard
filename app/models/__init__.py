"""
Exportación central de modelos de datos relacionales.
"""

from app.extensions import db, login_manager
from app.models.audit import AuditLog
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.router_event import RouterSyncLog
from app.models.schedule import AccessSchedule
from app.models.user import User, utc_now_naive


@login_manager.user_loader
def load_user(user_id: str):
    """Carga el usuario autenticado verificando que exista y continúe activo."""
    if not user_id:
        return None
    try:
        user = db.session.get(User, int(user_id))
        if user and user.is_active:
            return user
    except (ValueError, TypeError):
        return None
    return None


__all__ = [
    "User",
    "Device",
    "AccessPolicy",
    "AccessSchedule",
    "AuditLog",
    "RouterSyncLog",
    "utc_now_naive",
]

