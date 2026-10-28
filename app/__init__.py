"""
Application Factory principal para el proyecto de tesis:
"Sistema web para administración de dispositivos y políticas de acceso
en redes domésticas mediante gestión de direcciones IP"
"""

import os
import click
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError
from app.extensions import csrf, db, login_manager, migrate
from app.models import AccessPolicy, AccessSchedule, AuditLog, Device, RouterSyncLog, User
from app.routes import register_blueprints
from app.services.demo_seed_service import clear_laboratory_demo_data, seed_laboratory_demo_data
from app.services.router_adapter import get_router_adapter
from app.services.user_service import create_user
from app.services.validators import ValidationError
from config import CONFIG_BY_NAME


def create_app(config_name: str | None = None) -> Flask:
    """Crea y configura una instancia de la aplicación Flask."""
    if not config_name:
        config_name = os.environ.get("FLASK_ENV", "development")
    config_cls = CONFIG_BY_NAME.get(config_name, CONFIG_BY_NAME["default"])

    app = Flask(__name__)
    app.config.from_object(config_cls)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Registrar blueprints
    register_blueprints(app)

    # Variables globales para plantillas Jinja2
    @app.context_processor
    def inject_global_context():
        adapter = get_router_adapter()
        return {
            "PROJECT_TITLE": app.config.get("PROJECT_TITLE"),
            "PROJECT_SHORT_NAME": app.config.get("PROJECT_SHORT_NAME"),
            "PROJECT_VERSION": app.config.get("PROJECT_VERSION"),
            "ADAPTER_MODE": adapter.adapter_id,
            "ADAPTER_DISPLAY_NAME": adapter.display_name,
            "ADAPTER_IS_SIMULATED": adapter.is_simulated,
        }

    # Cabeceras HTTP defensivas
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Manejadores de errores seguros (sin exponer trazas internas al usuario)
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        flash(
            "La solicitud fue rechazada por protección CSRF (token faltante o expirado). "
            "Recargue el formulario e intente nuevamente.",
            "error",
        )
        return render_template("errors/400_csrf.html", reason=error.description), 400

    @app.errorhandler(403)
    def handle_forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def handle_not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def handle_internal_error(_error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    # Comandos CLI de inicialización y laboratorio
    register_cli_commands(app)

    return app


def register_cli_commands(app: Flask) -> None:
    """Registra comandos CLI documentados para inicializar BD, administrador y datos demo."""

    @app.cli.command("init-db")
    def init_db_command():
        """Crea las tablas del esquema relacional en la base de datos configurada."""
        db.create_all()
        click.secho("[OK] Esquema de base de datos verificado/creado correctamente.", fg="green")

    @app.cli.command("init-admin")
    @click.option("--username", default=None, help="Nombre de usuario del administrador inicial.")
    @click.option("--email", default=None, help="Correo electrónico del administrador.")
    @click.option("--full-name", default="Administrador de Red Doméstica", help="Nombre completo.")
    @click.option("--password", default=None, help="Contraseña (mínimo 8 caracteres).")
    def init_admin_command(username, email, full_name, password):
        """
        Crea el usuario administrador inicial leyendo variables de entorno
        (ADMIN_INIT_USERNAME, ADMIN_INIT_EMAIL, ADMIN_INIT_PASSWORD) o solicitándolas
        de forma interactiva segura sin credenciales fijas en el código.
        """
        db.create_all()
        resolved_username = username or os.environ.get("ADMIN_INIT_USERNAME")
        if not resolved_username:
            resolved_username = click.prompt("Nombre de usuario administrador", default="admin_red")

        resolved_email = email or os.environ.get("ADMIN_INIT_EMAIL")
        if not resolved_email:
            resolved_email = click.prompt("Correo electrónico", default="admin@red-domestica.local")

        resolved_password = password or os.environ.get("ADMIN_INIT_PASSWORD")
        if not resolved_password:
            resolved_password = click.prompt(
                "Contraseña del administrador (mínimo 8 caracteres)",
                hide_input=True,
                confirmation_prompt=True,
            )

        existing = User.query.filter_by(username=resolved_username).first()
        if existing:
            click.secho(
                f"[AVISO] El usuario '{resolved_username}' ya existe en la base de datos.",
                fg="yellow",
            )
            return

        try:
            user = create_user(
                username=resolved_username,
                email=resolved_email,
                full_name=full_name,
                password=resolved_password,
                role="admin",
                is_active=True,
            )
            click.secho(
                f"[OK] Administrador '{user.username}' ({user.email}) creado exitosamente.",
                fg="green",
            )
        except ValidationError as exc:
            click.secho(f"[ERROR] {exc}", fg="red")
            raise SystemExit(1)

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Carga dispositivos, políticas y horarios simulados para demostración en laboratorio."""
        db.create_all()
        admin_user = User.query.filter_by(role="admin").first()
        counts = seed_laboratory_demo_data(user_id=admin_user.id if admin_user else None)
        click.secho(
            f"[OK] Datos de laboratorio cargados: {counts['devices']} dispositivos, "
            f"{counts['policies']} políticas y {counts['schedules']} horarios.",
            fg="green",
        )

    @app.cli.command("clear-demo")
    def clear_demo_command():
        """Elimina todos los registros marcados como datos de demostración (`is_demo=True`)."""
        counts = clear_laboratory_demo_data()
        click.secho(
            f"[OK] Datos de demostración eliminados: {counts['devices']} dispositivos, "
            f"{counts['policies']} políticas y {counts['schedules']} horarios.",
            fg="cyan",
        )

