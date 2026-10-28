"""
Decoradores de autorización basada en roles para rutas privadas.
"""

from functools import wraps
from flask import abort, flash, redirect, request, url_for
from flask_login import current_user


def write_permission_required(view_func):
    """Exige que el usuario autenticado tenga permisos de escritura (admin u operator)."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        if not current_user.can_modify:
            flash(
                "Su cuenta tiene rol de solo lectura (Auditor) y no está autorizada para modificar registros.",
                "warning",
            )
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


def admin_required(view_func):
    """Exige que el usuario autenticado tenga rol de Administrador General."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))
        if not current_user.is_admin:
            flash("Esta sección requiere privilegios de Administrador General.", "error")
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped

