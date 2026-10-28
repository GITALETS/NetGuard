"""
Rutas de Configuración, Diagnóstico Seguro del Sistema y Estado del Adaptador de Router.
"""

import platform
import time
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import text
from app.extensions import db
from app.models.audit import AuditLog
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.router_event import RouterSyncLog
from app.models.schedule import AccessSchedule
from app.models.user import User
from app.routes.decorators import write_permission_required
from app.services.audit_service import log_audit_event
from app.services.demo_seed_service import clear_laboratory_demo_data, seed_laboratory_demo_data
from app.services.router_adapter import get_router_adapter
from config import sanitize_database_uri

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


def _probe_database_health() -> dict:
    """Realiza una comprobación en vivo de la conexión SQL sin exponer credenciales."""
    raw_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    safe_uri = sanitize_database_uri(raw_uri)
    dialect = db.engine.dialect.name

    start_ns = time.perf_counter_ns()
    try:
        db.session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)
        connected = True
        error_msg = None
    except Exception:
        latency_ms = None
        connected = False
        error_msg = "Fallo al verificar la conexión con el motor de base de datos."

    engine_label_map = {
        "mysql": "MySQL / MariaDB (Motor Relacional Principal)",
        "mariadb": "MariaDB (Motor Relacional Compatible)",
        "sqlite": "SQLite (Motor Local de Laboratorio / Pruebas)",
    }

    return {
        "connected": connected,
        "dialect": dialect,
        "engine_label": engine_label_map.get(dialect, dialect.upper()),
        "safe_uri": safe_uri,
        "latency_ms": latency_ms,
        "error_msg": error_msg,
        "record_counts": {
            "users": User.query.count(),
            "devices": Device.query.count(),
            "demo_devices": Device.query.filter_by(is_demo=True).count(),
            "policies": AccessPolicy.query.count(),
            "schedules": AccessSchedule.query.count(),
            "audit_logs": AuditLog.query.count(),
            "router_sync_logs": RouterSyncLog.query.count(),
        },
    }


@settings_bp.route("/")
@login_required
def index():
    db_health = _probe_database_health()
    adapter_info = get_router_adapter().get_diagnostics()
    recent_sync_logs = RouterSyncLog.query.order_by(RouterSyncLog.created_at.desc()).limit(10).all()

    app_info = {
        "project_title": current_app.config.get("PROJECT_TITLE"),
        "short_name": current_app.config.get("PROJECT_SHORT_NAME"),
        "version": current_app.config.get("PROJECT_VERSION"),
        "environment": current_app.config.get("ENV_NAME", "development"),
        "python_version": platform.python_version(),
        "default_scope": current_app.config.get("DEFAULT_NETWORK_SCOPE", "192.168.1.0/24"),
        "default_gateway": current_app.config.get("DEFAULT_GATEWAY_IP", "192.168.1.1"),
        "csrf_enabled": bool(current_app.config.get("WTF_CSRF_ENABLED", True)),
        "session_httponly": bool(current_app.config.get("SESSION_COOKIE_HTTPONLY", True)),
        "session_samesite": current_app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
    }

    return render_template(
        "settings/index.html",
        app_info=app_info,
        db_health=db_health,
        adapter_info=adapter_info,
        recent_sync_logs=recent_sync_logs,
    )


@settings_bp.route("/switch-adapter", methods=["POST"])
@login_required
@write_permission_required
def switch_adapter():
    mode = (request.form.get("adapter_mode") or "").strip()
    if mode not in ("lab_simulator", "passive_only"):
        flash("Modo de adaptador inválido.", "error")
        return redirect(url_for("settings.index"))

    current_app.config["ROUTER_ADAPTER_MODE"] = mode
    adapter_diag = get_router_adapter(mode).get_diagnostics()
    log_audit_event(
        event_type="ROUTER_ADAPTER_MODE_CHANGED",
        module="system",
        description=f"Cambio de modo del adaptador de router a '{adapter_diag['display_name']}'.",
        severity="info",
        user_id=current_user.id,
        metadata={"adapter_mode": mode},
        commit=True,
    )
    flash(f"Modo de operación cambiado a: {adapter_diag['display_name']}.", "success")
    return redirect(url_for("settings.index"))


@settings_bp.route("/seed-demo", methods=["POST"])
@login_required
@write_permission_required
def seed_demo():
    counts = seed_laboratory_demo_data(user_id=current_user.id)
    flash(
        f"Datos de demostración de laboratorio cargados: {counts['devices']} dispositivos, "
        f"{counts['policies']} políticas y {counts['schedules']} horarios.",
        "success",
    )
    return redirect(url_for("settings.index"))


@settings_bp.route("/clear-demo", methods=["POST"])
@login_required
@write_permission_required
def clear_demo():
    counts = clear_laboratory_demo_data(user_id=current_user.id)
    flash(
        f"Datos de demostración eliminados: {counts['devices']} dispositivos, "
        f"{counts['policies']} políticas y {counts['schedules']} horarios.",
        "info",
    )
    return redirect(url_for("settings.index"))

