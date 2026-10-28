"""
Modelo de Historial y Auditoría (AuditLog).
Registra eventos importantes del sistema sin exponer contraseñas, tokens ni secretos.
"""

import json
from typing import Any, Dict
from app.extensions import db
from app.models.user import utc_now_naive


class AuditLog(db.Model):
    """Registro inmutable de eventos administrativos y de seguridad."""

    __tablename__ = "audit_logs"

    VALID_SEVERITIES = ("info", "warning", "error", "security")
    SEVERITY_LABELS = {
        "info": "Informativo",
        "warning": "Advertencia",
        "error": "Error Operativo",
        "security": "Seguridad / Acceso",
    }

    MODULE_LABELS = {
        "auth": "Autenticación",
        "devices": "Dispositivos",
        "policies": "Políticas de Acceso",
        "schedules": "Horarios",
        "users": "Usuarios",
        "router_adapter": "Adaptador Router",
        "system": "Sistema",
    }

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive, index=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    module = db.Column(db.String(40), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, default="info", index=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    username_snapshot = db.Column(db.String(64), nullable=True)
    ip_origin = db.Column(db.String(45), nullable=True)
    target_type = db.Column(db.String(40), nullable=True)
    target_id = db.Column(db.String(40), nullable=True)
    description = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)

    user = db.relationship("User", backref=db.backref("audit_events", lazy="dynamic"))

    @property
    def severity_label(self) -> str:
        return self.SEVERITY_LABELS.get(self.severity, self.severity)

    @property
    def module_label(self) -> str:
        return self.MODULE_LABELS.get(self.module, self.module)

    @property
    def metadata_dict(self) -> Dict[str, Any]:
        if not self.metadata_json:
            return {}
        try:
            data = json.loads(self.metadata_json)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def __repr__(self) -> str:
        return f"<AuditLog {self.id} [{self.severity}] {self.event_type}>"

