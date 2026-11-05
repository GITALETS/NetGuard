"""
Modelo de Categorías Dinámicas del Sistema.
Permite a administradores y superadministradores registrar nuevas categorías
de dispositivos, perfiles de red y destinos de filtrado sin modificar el código fuente.
"""

from app.extensions import db
from app.models.user import utc_now_naive


class SystemCategory(db.Model):
    """
    Entidad relacional para categorización extensible del sistema.
    Tipos soportados:
    - device_type: Tipos de hardware o dispositivos (ej. Smart Speaker, NAS, Cámara IP).
    - device_profile: Perfiles de uso y segmentación familiar (ej. Teletrabajo, Invitados VIP).
    - policy_target: Categorías o etiquetas de destinos y servicios (ej. Redes Sociales, Videojuegos).
    """

    __tablename__ = "system_categories"
    __table_args__ = (
        db.UniqueConstraint("category_type", "code", name="uq_cat_type_code"),
    )

    VALID_CATEGORY_TYPES = ("device_type", "device_profile", "policy_target")
    CATEGORY_TYPE_LABELS = {
        "device_type": "Tipo de Dispositivo",
        "device_profile": "Perfil Familiar de Red",
        "policy_target": "Categoría de Navegación / Destino",
    }

    id = db.Column(db.Integer, primary_key=True)
    category_type = db.Column(db.String(32), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_system_default = db.Column(db.Boolean, nullable=False, default=False)
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

    created_by = db.relationship("User", backref=db.backref("created_categories", lazy="dynamic"))

    @property
    def type_label(self) -> str:
        """Devuelve la etiqueta legible del tipo de categoría."""
        return self.CATEGORY_TYPE_LABELS.get(self.category_type, self.category_type)

    def __repr__(self) -> str:
        return f"<SystemCategory {self.category_type}:{self.code} '{self.name}'>"

