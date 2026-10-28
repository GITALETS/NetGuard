"""
Configuración central de la aplicación web.
Proyecto: "Sistema web para administración de dispositivos y políticas de acceso
en redes domésticas mediante gestión de direcciones IP"
"""

import os
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

PROJECT_TITLE = (
    "Sistema web para administración de dispositivos y políticas de acceso "
    "en redes domésticas mediante gestión de direcciones IP"
)
PROJECT_SHORT_NAME = "NetGuard Home IP"
PROJECT_VERSION = "1.0"


def sanitize_database_uri(uri: str) -> str:
    """Oculta credenciales sensibles de una cadena de conexión para diagnóstico seguro."""
    if not uri:
        return "No configurada"
    if uri.startswith("sqlite"):
        return uri
    try:
        parts = urlsplit(uri)
        if parts.password:
            safe_netloc = f"{parts.username}:***@{parts.hostname}"
            if parts.port:
                safe_netloc += f":{parts.port}"
            return urlunsplit((parts.scheme, safe_netloc, parts.path, parts.query, parts.fragment))
        return uri
    except Exception:
        return "URI protegida (credenciales ocultas)"


class Config:
    """Configuración base compartida por todos los entornos."""

    PROJECT_TITLE = PROJECT_TITLE
    PROJECT_SHORT_NAME = PROJECT_SHORT_NAME
    PROJECT_VERSION = PROJECT_VERSION

    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # Motor principal previsto: MySQL / MariaDB mediante PyMySQL.
    # Si no se especifica DATABASE_URL en el entorno local, utiliza una base en instance/
    # para permitir la ejecución inmediata en laboratorio universitario.
    INSTANCE_DIR = BASE_DIR / "instance"
    INSTANCE_DIR.mkdir(exist_ok=True)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{(INSTANCE_DIR / 'red_domestica_lab.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
    }

    # Parámetros de seguridad de sesión y CSRF
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Parámetros de red doméstica administrada y adaptador de router
    DEFAULT_NETWORK_SCOPE = os.environ.get("DEFAULT_NETWORK_SCOPE", "192.168.1.0/24")
    DEFAULT_GATEWAY_IP = os.environ.get("DEFAULT_GATEWAY_IP", "192.168.1.1")
    ROUTER_ADAPTER_MODE = os.environ.get("ROUTER_ADAPTER_MODE", "lab_simulator")


class DevelopmentConfig(Config):
    """Configuración de desarrollo y demostración en laboratorio."""

    DEBUG = True
    ENV_NAME = "development"


class TestingConfig(Config):
    """Configuración aislada para pruebas automatizadas con pytest."""

    TESTING = True
    DEBUG = False
    ENV_NAME = "testing"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = True
    ROUTER_ADAPTER_MODE = "lab_simulator"


class ProductionConfig(Config):
    """Configuración endurecida para despliegue."""

    DEBUG = False
    ENV_NAME = "production"
    SESSION_COOKIE_SECURE = True


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

