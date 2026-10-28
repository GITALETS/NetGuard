"""
Registro centralizado de Blueprints de rutas HTTP.
"""

from flask import Flask
from app.routes.audit import audit_bp
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.devices import devices_bp
from app.routes.policies import policies_bp
from app.routes.schedules import schedules_bp
from app.routes.settings import settings_bp
from app.routes.users import users_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(devices_bp)
    app.register_blueprint(policies_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(settings_bp)

