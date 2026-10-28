"""
Servicio de administración de usuarios del sistema y autenticación segura.
"""

import re
from typing import Any, Dict, Optional
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.extensions import db
from app.models.user import User, utc_now_naive
from app.services.audit_service import log_audit_event
from app.services.validators import ValidationError

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]{3,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def create_user(
    username: str,
    email: str,
    full_name: str,
    password: str,
    role: str = "admin",
    is_active: bool = True,
    actor_user_id: Optional[int] = None,
) -> User:
    """Crea un usuario del sistema aplicando hash seguro de contraseña y validaciones."""
    clean_username = (username or "").strip()
    clean_email = (email or "").strip().lower()
    clean_name = (full_name or "").strip()
    clean_role = (role or "operator").strip()

    if not USERNAME_RE.match(clean_username):
        raise ValidationError(
            "El nombre de usuario debe tener entre 3 y 64 caracteres alfanuméricos (letras, números, _, ., -)."
        )
    if not EMAIL_RE.match(clean_email):
        raise ValidationError("El correo electrónico proporcionado no tiene un formato válido.")
    if not clean_name or len(clean_name) < 2:
        raise ValidationError("El nombre completo del usuario es obligatorio.")
    if clean_role not in User.VALID_ROLES:
        raise ValidationError(f"Rol de usuario inválido: '{clean_role}'.")
    if not password or len(password) < 8:
        raise ValidationError("La contraseña debe tener al menos 8 caracteres de longitud.")

    if User.query.filter(db.func.lower(User.username) == clean_username.lower()).first():
        raise ValidationError(f"El nombre de usuario '{clean_username}' ya está registrado.")
    if User.query.filter(db.func.lower(User.email) == clean_email).first():
        raise ValidationError(f"El correo electrónico '{clean_email}' ya está registrado.")

    user = User(
        username=clean_username,
        email=clean_email,
        full_name=clean_name,
        role=clean_role,
        is_active=bool(is_active),
    )
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.flush()
        log_audit_event(
            event_type="USER_CREATED",
            module="users",
            description=f"Alta de usuario del sistema '{user.username}' con rol '{user.role_label}'.",
            severity="security",
            user_id=actor_user_id,
            target_type="user",
            target_id=user.id,
            metadata={"username": user.username, "role": user.role, "is_active": user.is_active},
        )
        db.session.commit()
        return user
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError("El nombre de usuario o correo electrónico ya se encuentra en uso.") from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al crear el usuario.") from exc


def update_user_account(
    target_user: User,
    data: Dict[str, Any],
    actor_user: Optional[User] = None,
) -> User:
    """Actualiza datos administrativos, rol, estado o contraseña de un usuario."""
    clean_name = (data.get("full_name") or target_user.full_name).strip()
    clean_email = (data.get("email") or target_user.email).strip().lower()
    new_role = (data.get("role") or target_user.role).strip()
    new_active = bool(data.get("is_active", target_user.is_active))
    new_password = data.get("new_password")

    if not EMAIL_RE.match(clean_email):
        raise ValidationError("El correo electrónico proporcionado no es válido.")
    if new_role not in User.VALID_ROLES:
        raise ValidationError("Rol de usuario inválido.")

    existing_email = User.query.filter(
        db.func.lower(User.email) == clean_email,
        User.id != target_user.id,
    ).first()
    if existing_email:
        raise ValidationError(f"El correo '{clean_email}' ya está asignado a otro usuario.")

    # Impedir que un administrador se desactive a sí mismo o se quite el rol admin siendo el único
    if actor_user and actor_user.id == target_user.id:
        if not new_active:
            raise ValidationError("No puede desactivar su propia cuenta en sesión activa.")
        if target_user.role == "admin" and new_role != "admin":
            raise ValidationError("No puede degradar su propio rol de Administrador General.")

    if target_user.role == "admin" and (not new_active or new_role != "admin"):
        other_active_admins = User.query.filter(
            User.role == "admin",
            User.is_active.is_(True),
            User.id != target_user.id,
        ).count()
        if other_active_admins == 0:
            raise ValidationError(
                "Operación denegada: el sistema debe conservar al menos un Administrador General activo."
            )

    target_user.full_name = clean_name
    target_user.email = clean_email
    target_user.role = new_role
    target_user.is_active = new_active

    password_changed = False
    if new_password:
        if len(new_password) < 8:
            raise ValidationError("La nueva contraseña debe tener al menos 8 caracteres.")
        target_user.set_password(new_password)
        password_changed = True

    try:
        log_audit_event(
            event_type="USER_UPDATED",
            module="users",
            description=(
                f"Actualización de cuenta de usuario '{target_user.username}' "
                f"[Rol: {target_user.role_label}, Activo: {target_user.is_active}]."
            ),
            severity="security",
            user_id=actor_user.id if actor_user else None,
            target_type="user",
            target_id=target_user.id,
            metadata={
                "username": target_user.username,
                "role": target_user.role,
                "is_active": target_user.is_active,
                "password_updated": password_changed,
            },
        )
        db.session.commit()
        return target_user
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error de base de datos al actualizar el usuario.") from exc


def authenticate_user(username_or_email: str, password: str) -> Optional[User]:
    """
    Verifica credenciales de inicio de sesión y registra el resultado en auditoría.
    No revela en los mensajes de error si el usuario existe o cuál campo falló.
    """
    identifier = (username_or_email or "").strip()
    if not identifier or not password:
        return None

    user = User.query.filter(
        db.or_(
            db.func.lower(User.username) == identifier.lower(),
            db.func.lower(User.email) == identifier.lower(),
        )
    ).first()

    if not user or not user.check_password(password):
        log_audit_event(
            event_type="AUTH_LOGIN_FAILED",
            module="auth",
            description=f"Intento fallido de inicio de sesión para identificador '{identifier[:40]}'.",
            severity="security",
            user_id=user.id if user else None,
            username_snapshot=user.username if user else identifier[:40],
            metadata={"reason": "invalid_credentials"},
            commit=True,
        )
        return None

    if not user.is_active:
        log_audit_event(
            event_type="AUTH_LOGIN_INACTIVE",
            module="auth",
            description=f"Intento de acceso con cuenta desactivada '{user.username}'.",
            severity="security",
            user_id=user.id,
            username_snapshot=user.username,
            metadata={"reason": "account_inactive"},
            commit=True,
        )
        return None

    user.last_login_at = utc_now_naive()
    log_audit_event(
        event_type="AUTH_LOGIN_SUCCESS",
        module="auth",
        description=f"Inicio de sesión exitoso del usuario '{user.username}' ({user.role_label}).",
        severity="security",
        user_id=user.id,
        username_snapshot=user.username,
        commit=True,
    )
    return user

