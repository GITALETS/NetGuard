"""
Modelo de Política de Acceso asociada a un dispositivo.
Distingue entre el estado administrativo/vigencia temporal de la política y
su estado real de aplicación en el adaptador del router.
"""

from datetime import datetime
from typing import Optional
from app.extensions import db
from app.models.user import utc_now_naive


class AccessPolicy(db.Model):
    """Representa una política de acceso configurada para un dispositivo."""

    __tablename__ = "access_policies"

    VALID_POLICY_TYPES = (
        "administrative_auth",
        "temporary_access",
        "allowed_schedule",
        "navigation_restriction",
        "permanent_access",
        "intermittent_intermediary",
    )
    POLICY_TYPE_LABELS = {
        "administrative_auth": "1. Autorización Administrativa",
        "temporary_access": "2. Acceso Temporal",
        "allowed_schedule": "3. Horarios Permitidos",
        "navigation_restriction": "4. Restricciones de Navegación Configurables",
        "permanent_access": "5. Política de Acceso Permanente",
        "intermittent_intermediary": "6. Control Intermediario con Intermitencia (Páginas / Servicios)",
    }

    VALID_TARGET_SCOPES = ("all_traffic", "specific_domain", "web_category")
    TARGET_SCOPE_LABELS = {
        "all_traffic": "Tráfico General de Red (Todo Internet)",
        "specific_domain": "Página o Dominio Específico (ej. youtube.com)",
        "web_category": "Categoría de Contenido (Redes Sociales, Videojuegos)",
    }

    VALID_ACTIONS = ("allow", "restrict", "block")
    ACTION_LABELS = {
        "allow": "Permitir Acceso",
        "restrict": "Restringir / Filtrar",
        "block": "Bloquear Tráfico",
    }

    VALID_STATUSES = ("active", "paused", "revoked", "expired")
    STATUS_LABELS = {
        "active": "Vigente",
        "scheduled": "Programada (Aún no inicia)",
        "paused": "Pausada",
        "revoked": "Revocada",
        "expired": "Expirada",
    }

    VALID_ENFORCEMENT = (
        "stored_in_db",
        "simulated_in_lab",
        "applied_in_router",
        "unsupported_by_router",
        "sync_error",
    )
    ENFORCEMENT_LABELS = {
        "stored_in_db": "Registrada en BD (No aplicada al tráfico real)",
        "simulated_in_lab": "Aplicada en Simulador de Laboratorio",
        "applied_in_router": "Confirmada en Router Real",
        "unsupported_by_router": "Sin soporte de hardware en Router actual",
        "sync_error": "Fallo al comunicar con el Router",
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    device_id = db.Column(
        db.Integer,
        db.ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_type = db.Column(db.String(40), nullable=False, index=True)
    action = db.Column(db.String(24), nullable=False, default="allow")
    priority = db.Column(db.Integer, nullable=False, default=50)
    status = db.Column(db.String(24), nullable=False, default="active", index=True)
    valid_from = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    valid_until = db.Column(db.DateTime, nullable=True)
    navigation_profile = db.Column(db.String(160), nullable=True)
    target_scope = db.Column(db.String(32), nullable=False, default="all_traffic")
    target_domain = db.Column(db.String(255), nullable=True)
    is_intermittent = db.Column(db.Boolean, nullable=False, default=False)
    interval_active_minutes = db.Column(db.Integer, nullable=False, default=30)
    interval_pause_minutes = db.Column(db.Integer, nullable=False, default=15)
    current_cycle_state = db.Column(db.String(32), nullable=False, default="active_window")
    next_cycle_switch_at = db.Column(db.DateTime, nullable=True)
    observations = db.Column(db.Text, nullable=True)
    enforcement_status = db.Column(
        db.String(32),
        nullable=False,
        default="stored_in_db",
    )
    last_evaluated_at = db.Column(db.DateTime, nullable=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )

    device = db.relationship("Device", back_populates="policies")
    created_by = db.relationship("User", backref=db.backref("created_policies", lazy="dynamic"))
    schedules = db.relationship(
        "AccessSchedule",
        back_populates="policy",
        cascade="all, delete-orphan",
    )

    def is_expired_at(self, reference_time: Optional[datetime] = None) -> bool:
        """Determina si la política ha superado su fecha/hora de finalización."""
        now = reference_time or utc_now_naive()
        if self.status == "expired":
            return True
        if self.valid_until is not None and now >= self.valid_until:
            return True
        return False

    def effective_status_at(self, reference_time: Optional[datetime] = None) -> str:
        """
        Calcula el estado efectivo considerando el reloj actual.
        Una política cuya fecha final ha pasado NUNCA se devuelve como vigente.
        """
        now = reference_time or utc_now_naive()
        if self.status in ("revoked", "paused", "expired"):
            return self.status
        if self.valid_until is not None and now >= self.valid_until:
            return "expired"
        if self.valid_from is not None and now < self.valid_from:
            return "scheduled"
        return "active"

    def is_currently_effective(self, reference_time: Optional[datetime] = None) -> bool:
        """Indica si la política está efectivamente vigente en el instante evaluado."""
        return self.effective_status_at(reference_time) == "active"

    @property
    def effective_status(self) -> str:
        return self.effective_status_at()

    @property
    def effective_status_label(self) -> str:
        eff = self.effective_status
        return self.STATUS_LABELS.get(eff, eff)

    @property
    def policy_type_label(self) -> str:
        return self.POLICY_TYPE_LABELS.get(self.policy_type, self.policy_type)

    @property
    def target_scope_label(self) -> str:
        """Devuelve la etiqueta legible del ámbito o destino de la política."""
        return self.TARGET_SCOPE_LABELS.get(self.target_scope, self.target_scope)

    @property
    def intermittent_summary(self) -> Optional[str]:
        """Devuelve un resumen técnico amigable de los intervalos de intermitencia."""
        if not self.is_intermittent:
            return None
        target = self.target_domain or self.navigation_profile or "Internet General"
        return f"{self.interval_active_minutes} min activo / {self.interval_pause_minutes} min pausa ({target})"

    @property
    def action_label(self) -> str:
        return self.ACTION_LABELS.get(self.action, self.action)

    @property
    def enforcement_label(self) -> str:
        return self.ENFORCEMENT_LABELS.get(self.enforcement_status, self.enforcement_status)

    def __repr__(self) -> str:
        return f"<AccessPolicy {self.id} {self.name} ({self.policy_type})>"

