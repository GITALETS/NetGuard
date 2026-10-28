"""
Modelo de Dispositivo registrado en la red doméstica administrada.
Distingue explícitamente entre identificador interno, nombre, dirección IP
(temporal o reservada), dirección MAC y estado de sincronización con el router.
"""

from app.extensions import db
from app.models.user import utc_now_naive


class Device(db.Model):
    """Representa un dispositivo registrado bajo un ámbito de red doméstica."""

    __tablename__ = "devices"
    __table_args__ = (
        db.UniqueConstraint("ip_address", "network_scope", name="uq_device_ip_scope"),
    )

    VALID_TYPES = (
        "workstation",
        "laptop",
        "smartphone",
        "tablet",
        "iot",
        "smart_tv",
        "console",
        "server",
        "printer",
        "other",
    )
    TYPE_LABELS = {
        "workstation": "PC de Escritorio / Estación",
        "laptop": "Computadora Portátil",
        "smartphone": "Teléfono Inteligente",
        "tablet": "Tableta",
        "iot": "Dispositivo IoT / Domótica",
        "smart_tv": "Smart TV / Multimedia",
        "console": "Consola de Videojuegos",
        "server": "Servidor Local / NAS",
        "printer": "Impresora de Red",
        "other": "Otro Dispositivo",
    }

    VALID_ADMIN_STATUSES = ("authorized", "restricted", "blocked", "pending")
    ADMIN_STATUS_LABELS = {
        "authorized": "Autorizado",
        "restricted": "Restringido (Con Políticas)",
        "blocked": "Bloqueado / No Autorizado",
        "pending": "Pendiente de Revisión",
    }

    VALID_PROFILES = ("family", "child", "guest", "iot", "other")
    PROFILE_LABELS = {
        "family": "Familiar (Adultos / General)",
        "child": "Menor (Niños / Estudiantes con supervisión)",
        "guest": "Visita (Invitados temporales)",
        "iot": "Hogar Inteligente / IoT (Smart TV, Cámaras, Consolas)",
        "other": "Otro Perfil",
    }

    VALID_IP_ASSIGNMENTS = ("static_manual", "dhcp_reservation", "dhcp_dynamic_observed")
    IP_ASSIGNMENT_LABELS = {
        "static_manual": "IP Estática Configurada",
        "dhcp_reservation": "Reserva DHCP por MAC",
        "dhcp_dynamic_observed": "DHCP Dinámico (Temporal / Volátil)",
    }

    VALID_ROUTER_SYNC = (
        "only_in_db",
        "simulated_applied",
        "applied_confirmed",
        "not_supported",
        "sync_error",
    )
    ROUTER_SYNC_LABELS = {
        "only_in_db": "Solo registrado en BD (Sin aplicar en red)",
        "simulated_applied": "Aplicado en Simulador de Laboratorio",
        "applied_confirmed": "Confirmado en Router Real",
        "not_supported": "Sin integración de Router activa",
        "sync_error": "Error de sincronización con Router",
    }

    id = db.Column(db.Integer, primary_key=True)
    internal_code = db.Column(db.String(24), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    hostname = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    network_scope = db.Column(db.String(45), nullable=False, default="192.168.1.0/24")
    ip_assignment_type = db.Column(
        db.String(32),
        nullable=False,
        default="dhcp_reservation",
    )
    mac_address = db.Column(db.String(17), unique=True, nullable=True)
    device_type = db.Column(db.String(32), nullable=False, default="other", index=True)
    profile = db.Column(db.String(32), nullable=False, default="family", index=True)
    owner_label = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    admin_status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    router_sync_status = db.Column(db.String(32), nullable=False, default="only_in_db")
    last_synced_at = db.Column(db.DateTime, nullable=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    registered_by_id = db.Column(
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

    registered_by = db.relationship("User", backref=db.backref("registered_devices", lazy="dynamic"))
    policies = db.relationship(
        "AccessPolicy",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="AccessPolicy.priority.asc(), AccessPolicy.created_at.desc()",
    )
    schedules = db.relationship(
        "AccessSchedule",
        back_populates="device",
        cascade="all, delete-orphan",
        order_by="AccessSchedule.created_at.desc()",
    )

    @property
    def type_label(self) -> str:
        return self.TYPE_LABELS.get(self.device_type, self.device_type)

    @property
    def profile_label(self) -> str:
        return self.PROFILE_LABELS.get(self.profile, self.profile)

    @property
    def admin_status_label(self) -> str:
        return self.ADMIN_STATUS_LABELS.get(self.admin_status, self.admin_status)

    @property
    def ip_assignment_label(self) -> str:
        return self.IP_ASSIGNMENT_LABELS.get(self.ip_assignment_type, self.ip_assignment_type)

    @property
    def router_sync_label(self) -> str:
        return self.ROUTER_SYNC_LABELS.get(self.router_sync_status, self.router_sync_status)

    @property
    def has_volatile_ip(self) -> bool:
        """Indica si la IP proviene de una concesión dinámica sin reserva permanente."""
        return self.ip_assignment_type == "dhcp_dynamic_observed"

    def __repr__(self) -> str:
        return f"<Device {self.internal_code} {self.name} ({self.ip_address})>"

