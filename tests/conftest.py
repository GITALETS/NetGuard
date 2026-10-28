"""
Configuración de fixtures de pytest con base de datos aislada en memoria.
Garantiza que ninguna prueba modifique bases de datos reales de desarrollo o producción.
"""

import re
import secrets
import pytest
from app import create_app
from app.extensions import db
from app.services.user_service import create_user

CSRF_INPUT_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')


def extract_csrf_token(response_html: str) -> str:
    """Extrae el token CSRF renderizado en un formulario HTML."""
    match = CSRF_INPUT_RE.search(response_html)
    assert match is not None, "No se encontró el campo csrf_token en el HTML de respuesta."
    return match.group(1)


@pytest.fixture()
def app():
    """Crea una instancia de la aplicación usando TestingConfig (SQLite en memoria aislada)."""
    test_app = create_app("testing")
    test_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": True,
            "SECRET_KEY": secrets.token_hex(32),
        }
    )

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Cliente de pruebas HTTP de Flask."""
    return app.test_client()


@pytest.fixture()
def admin_credentials():
    """Credenciales generadas dinámicamente por ejecución de prueba."""
    return {
        "username": "admin_test",
        "email": "admin_test@tesis.local",
        "full_name": "Administrador de Prueba",
        "password": f"ClaveSegura_{secrets.token_hex(6)}!",
    }


@pytest.fixture()
def admin_user(app, admin_credentials):
    """Crea un usuario administrador en la base de datos aislada de pruebas."""
    with app.app_context():
        user = create_user(
            username=admin_credentials["username"],
            email=admin_credentials["email"],
            full_name=admin_credentials["full_name"],
            password=admin_credentials["password"],
            role="admin",
            is_active=True,
        )
        return user.id


@pytest.fixture()
def auth_client(client, admin_user, admin_credentials):
    """Cliente HTTP autenticado como administrador con soporte CSRF."""
    get_resp = client.get("/auth/login")
    csrf_token = extract_csrf_token(get_resp.get_data(as_text=True))
    login_resp = client.post(
        "/auth/login",
        data={
            "csrf_token": csrf_token,
            "username": admin_credentials["username"],
            "password": admin_credentials["password"],
        },
        follow_redirects=True,
    )
    assert login_resp.status_code == 200
    return client

