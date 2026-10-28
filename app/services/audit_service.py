"""
Servicio de Historial y Auditoría.
Garantiza el registro estructurado de eventos y el filtrado automático de secretos,
contraseñas, hashes o tokens de sesión.
"""

import json
from typing import Any, Dict, Optional
from flask import has_request_context, request
from flask_login import current_user
from app.extensions import db
from app.models.audit import AuditLog

SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "csrf",
    "cookie",
    "session",
    "authorization",
    "api_key",
    "private_key",
    "hash",
)


def sanitize_metadata(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Elimina o redacta recursivamente cualquier clave sensible para evitar que
    contraseñas, secretos o tokens de sesión se almacenen en la bitácora.
    """
    if not data or not isinstance(data, dict):
        return {}

    cleaned: Dict[str, Any] = {}
    for key, val in data.items():
        key_str = str(key).lower()
        if any(sub in key_str for sub in SENSITIVE_KEY_SUBSTRINGS):
            cleaned[str(key)] = "[REDACTED]"
        elif isinstance(val, dict):
            cleaned[str(key)] = sanitize_metadata(val)
        elif isinstance(val, (list, tuple)):
            cleaned[str(key)] = [
                sanitize_metadata(item) if isinstance(item, dict) else str(item)
                for item in val
            ]
        else:
            cleaned[str(key)] = val
    return cleaned


def log_audit_event(
    event_type: str,
    module: str,
    description: str,
    severity: str = "info",
    user_id: Optional[int] = None,
    username_snapshot: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str | int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> AuditLog:
    """
    Registra un evento en la tabla `audit_logs`.
    Obtiene automáticamente el usuario autenticado y la IP de origen cuando existe
    un contexto de solicitud HTTP activo.
    """
    if severity not in AuditLog.VALID_SEVERITIES:
        severity = "info"

    resolved_user_id = user_id
    resolved_username = username_snapshot
    ip_origin = None

    if has_request_context():
        ip_origin = request.remote_addr or "127.0.0.1"
        try:
            if resolved_user_id is None and current_user and current_user.is_authenticated:
                resolved_user_id = current_user.id
                resolved_username = current_user.username
        except Exception:
            pass

    safe_meta = sanitize_metadata(metadata)
    metadata_str = json.dumps(safe_meta, ensure_ascii=False) if safe_meta else None

    entry = AuditLog(
        event_type=event_type.upper().strip(),
        module=module.lower().strip(),
        severity=severity,
        user_id=resolved_user_id,
        username_snapshot=resolved_username,
        ip_origin=ip_origin,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        description=description.strip(),
        metadata_json=metadata_str,
    )
    db.session.add(entry)
    if commit:
        db.session.commit()
    return entry

