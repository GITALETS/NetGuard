"""
Rutas de autenticación (Inicio y cierre de sesión seguros).
"""

from urllib.parse import urlsplit
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.user_service import authenticate_user

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _is_safe_next_url(target: str | None) -> bool:
    """Previene redirecciones abiertas verificando que el destino sea una ruta relativa interna."""
    if not target:
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc and target.startswith("/")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    has_any_user = User.query.count() > 0

    if request.method == "POST":
        identifier = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        remember = request.form.get("remember") == "1"

        if not identifier or not password:
            flash("Debe ingresar tanto su usuario/correo como su contraseña.", "error")
            return render_template("auth/login.html", has_any_user=has_any_user), 400

        user = authenticate_user(identifier, password)
        if not user:
            flash(
                "Credenciales inválidas o cuenta no autorizada. Verifique sus datos e intente nuevamente.",
                "error",
            )
            return render_template("auth/login.html", has_any_user=has_any_user), 401

        session.permanent = True
        login_user(user, remember=remember)
        flash(f"Bienvenido(a), {user.full_name}. Sesión iniciada correctamente.", "success")

        next_page = request.args.get("next") or request.form.get("next")
        if _is_safe_next_url(next_page):
            return redirect(next_page)
        return redirect(url_for("dashboard.index"))

    return render_template("auth/login.html", has_any_user=has_any_user)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    uname = current_user.username
    uid = current_user.id
    log_audit_event(
        event_type="AUTH_LOGOUT",
        module="auth",
        description=f"Cierre de sesión del usuario '{uname}'.",
        severity="security",
        user_id=uid,
        username_snapshot=uname,
        commit=True,
    )
    logout_user()
    session.clear()
    flash("Ha cerrado su sesión de forma segura.", "info")
    return redirect(url_for("auth.login"))

