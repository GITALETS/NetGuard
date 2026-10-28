"""
Pruebas automatizadas del módulo de Autenticación, Sesiones, Protección de Rutas Privadas y CSRF.
"""

import secrets
from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import User
from app.services.user_service import create_user
from tests.conftest import extract_csrf_token


def test_unauthenticated_access_redirects_to_login(client):
    """Comprueba que las rutas privadas redirigen a /auth/login cuando no hay sesión."""
    private_urls = [
        "/",
        "/devices/",
        "/devices/new",
        "/policies/",
        "/schedules/",
        "/audit/",
        "/settings/",
        "/users/",
    ]
    for url in private_urls:
        resp = client.get(url, follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


def test_valid_login_and_logout(client, app, admin_user, admin_credentials):
    """Comprueba el inicio y cierre de sesión válido y su registro en auditoría."""
    login_page = client.get("/auth/login")
    assert login_page.status_code == 200
    csrf_token = extract_csrf_token(login_page.get_data(as_text=True))

    resp = client.post(
        "/auth/login",
        data={
            "csrf_token": csrf_token,
            "username": admin_credentials["username"],
            "password": admin_credentials["password"],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Panel General de Estado de Red Doméstica" in html

    with app.app_context():
        log_entry = AuditLog.query.filter_by(event_type="AUTH_LOGIN_SUCCESS").first()
        assert log_entry is not None
        assert log_entry.username_snapshot == admin_credentials["username"]

    # Cerrar sesión
    csrf_logout = extract_csrf_token(html)
    logout_resp = client.post(
        "/auth/logout",
        data={"csrf_token": csrf_logout},
        follow_redirects=True,
    )
    assert logout_resp.status_code == 200
    assert "Ha cerrado su sesión de forma segura" in logout_resp.get_data(as_text=True)

    # Verificar que ya no puede acceder a ruta privada
    after_resp = client.get("/devices/", follow_redirects=False)
    assert after_resp.status_code == 302


def test_invalid_login_does_not_reveal_sensitive_info(client, app, admin_user, admin_credentials):
    """Comprueba que credenciales incorrectas devuelven 401 con mensaje genérico y registran fallo."""
    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.get_data(as_text=True))

    # Contraseña incorrecta para usuario existente
    resp_wrong_pwd = client.post(
        "/auth/login",
        data={
            "csrf_token": csrf_token,
            "username": admin_credentials["username"],
            "password": "PasswordIncorrecto123!",
        },
    )
    assert resp_wrong_pwd.status_code == 401
    msg_a = resp_wrong_pwd.get_data(as_text=True)
    assert "Credenciales inválidas o cuenta no autorizada" in msg_a

    # Usuario inexistente devuelve exactamente el mismo mensaje genérico
    resp_no_user = client.post(
        "/auth/login",
        data={
            "csrf_token": csrf_token,
            "username": "usuario_inexistente_xyz",
            "password": "PasswordIncorrecto123!",
        },
    )
    assert resp_no_user.status_code == 401
    msg_b = resp_no_user.get_data(as_text=True)
    assert "Credenciales inválidas o cuenta no autorizada" in msg_b

    with app.app_context():
        failed_logs = AuditLog.query.filter_by(event_type="AUTH_LOGIN_FAILED").count()
        assert failed_logs == 2


def test_inactive_user_cannot_login(client, app):
    """Comprueba que una cuenta desactivada no puede iniciar sesión."""
    pwd = f"ClaveInactiva_{secrets.token_hex(4)}!"
    with app.app_context():
        create_user(
            username="operador_inactivo",
            email="inactivo@tesis.local",
            full_name="Operador Suspendido",
            password=pwd,
            role="operator",
            is_active=False,
        )

    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.get_data(as_text=True))
    resp = client.post(
        "/auth/login",
        data={
            "csrf_token": csrf_token,
            "username": "operador_inactivo",
            "password": pwd,
        },
    )
    assert resp.status_code == 401


def test_csrf_protection_blocks_post_without_token(auth_client):
    """Comprueba que las solicitudes POST sin token CSRF válido son rechazadas con HTTP 400."""
    resp = auth_client.post(
        "/devices/new",
        data={
            "name": "Dispositivo Sin CSRF",
            "ip_address": "192.168.1.99",
            "network_scope": "192.168.1.0/24",
        },
    )
    assert resp.status_code == 400
    assert "CSRF" in resp.get_data(as_text=True)


def test_auditor_role_cannot_modify_resources(client, app):
    """Comprueba que el rol 'auditor' tiene acceso de lectura pero recibe 403 al intentar crear/editar."""
    pwd = f"ClaveAuditor_{secrets.token_hex(4)}!"
    with app.app_context():
        create_user(
            username="auditor_solo_lectura",
            email="auditor@tesis.local",
            full_name="Auditor Tesis",
            password=pwd,
            role="auditor",
            is_active=True,
        )

    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.get_data(as_text=True))
    client.post(
        "/auth/login",
        data={"csrf_token": csrf_token, "username": "auditor_solo_lectura", "password": pwd},
        follow_redirects=True,
    )

    # Puede consultar listado
    assert client.get("/devices/").status_code == 200
    # No puede acceder a formulario de creación ni a administración de usuarios
    assert client.get("/devices/new").status_code == 403
    assert client.get("/users/").status_code == 403

