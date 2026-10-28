"""
Modelo de Trazabilidad de Sincronización con el Adaptador del Router.
Mantiene separado el estado de configuración en la base de datos de las
operaciones solicitadas al adaptador y su confirmación (simulada o real).
"""

from app.extensions import db
from app.models.user import utc_now_naive


class RouterSyncLog(db.Model):
    """Registra la ejecución de operaciones sobre el adaptador del router."""

    __tablename__ = "router_sync_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive, index=True)
    adapter_name = db.Column(db.String(64), nullable=False)
    operation = db.Column(db.String(64), nullable=False)
    device_id = db.Column(
        db.Integer,
        db.ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    policy_id = db.Column(
        db.Integer,
        db.ForeignKey("access_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_simulated = db.Column(db.Boolean, nullable=False, default=True)
    result_status = db.Column(db.String(32), nullable=False)
    command_preview = db.Column(db.Text, nullable=True)
    response_detail = db.Column(db.Text, nullable=True)
    triggered_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    device = db.relationship("Device", backref=db.backref("router_sync_logs", lazy="dynamic"))
    policy = db.relationship("AccessPolicy", backref=db.backref("router_sync_logs", lazy="dynamic"))
    triggered_by = db.relationship("User")

    def __repr__(self) -> str:
        return f"<RouterSyncLog {self.id} {self.adapter_name}:{self.operation} ({self.result_status})>"

