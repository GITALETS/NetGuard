"""
Modelo de Usuario para autenticación y control de acceso al sistema.
"""

from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db


def utc_now_naive() -> datetime:
    """Devuelve la fecha/hora actual en UTC sin tzinfo para compatibilidad uniforme en SQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    """Representa un usuario autorizado para operar o auditar el sistema web."""

    __tablename__ = "users"

    VALID_ROLES = ("admin", "operator", "auditor")
    ROLE_LABELS = {
        "admin": "Administrador General",
        "operator": "Operador de Red",
        "auditor": "Auditor (Solo Lectura)",
    }

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="admin", index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )

    def set_password(self, raw_password: str) -> None:
        """Almacena la contraseña aplicando un algoritmo de hash criptográfico seguro."""
        if not raw_password or len(raw_password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Verifica una contraseña en texto plano contra el hash almacenado."""
        if not raw_password or not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw_password)

    @property
    def role_label(self) -> str:
        return self.ROLE_LABELS.get(self.role, self.role)

    @property
    def can_modify(self) -> bool:
        """Indica si el usuario tiene permisos de escritura sobre dispositivos y políticas."""
        return self.is_active and self.role in ("admin", "operator")

    @property
    def is_admin(self) -> bool:
        return self.is_active and self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"

