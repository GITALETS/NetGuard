"""
Pruebas unitarias y de integración para las observaciones de relatoría:
1. Superadministrador y matriz de permisos RBAC.
2. Categorías dinámicas creadas por administradores.
3. Intermediario con control de intermitencia y dominios específicos.
4. Control de acceso amigable para el rol Operador del Hogar.
5. Editor integrado dentro de la ficha técnica del dispositivo.
"""

from app.extensions import db
from app.models.category import SystemCategory
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.user import User
from app.services.category_service import create_custom_category, seed_default_system_categories
from app.services.device_service import create_device
from app.services.policy_service import create_policy
from app.services.router_adapter import execute_policy_router_sync
from app.services.user_service import create_user
from app.services.validators import ValidationError
from tests.conftest import extract_csrf_token


def test_superadmin_role_and_rbac(app):
    """Verifica la jerarquía de roles, creación de superadmin y restricciones de asignación."""
    with app.app_context():
        # 1. Crear Superadministrador inicial
        superadmin = create_user(
            username="super_master",
            email="master@red.local",
            full_name="Super Administrador de Red",
            password="SuperPassword123!",
            role="superadmin",
            is_active=True,
        )
        assert superadmin.is_superadmin is True
        assert superadmin.is_admin is True
        assert superadmin.can_manage_users is True
        assert superadmin.can_manage_categories is True
        assert superadmin.can_modify is True

        # 2. Superadmin puede crear un Administrador
        admin = create_user(
            username="admin_sub",
            email="admin_sub@red.local",
            full_name="Admin Secundario",
            password="AdminPassword123!",
            role="admin",
            is_active=True,
            actor_user_id=superadmin.id,
        )
        assert admin.is_superadmin is False
        assert admin.is_admin is True

        # 3. Un Administrador normal NO puede crear a otro Superadministrador
        try:
            create_user(
                username="fake_super",
                email="fake_super@red.local",
                full_name="Intento Ilegal",
                password="FakePassword123!",
                role="superadmin",
                is_active=True,
                actor_user_id=admin.id,
            )
            assert False, "Un administrador no debe poder crear un superadministrador."
        except ValidationError as exc:
            assert "Solo un Superadministrador activo" in str(exc)


def test_dynamic_categories_and_persistence(app, auth_client):
    """Verifica el alta de categorías dinámicas y su uso en dispositivos."""
    with app.app_context():
        # Poblar categorías base
        seed_default_system_categories()
        assert SystemCategory.query.count() >= 20

        # Crear categoría personalizada directamente con el servicio
        cat = create_custom_category(
            category_type="device_type",
            name="Consola Portátil de Juegos",
            description="Nintendo Switch y consolas móviles",
            code="handheld_console",
        )
        assert cat.id is not None
        assert cat.code == "handheld_console"

        # Registrar un dispositivo utilizando la nueva categoría dinámica
        dev = create_device(
            {
                "name": "Nintendo Switch OLED",
                "ip_address": "192.168.1.75",
                "network_scope": "192.168.1.0/24",
                "device_type": "handheld_console",
                "profile": "child",
                "admin_status": "authorized",
            }
        )
        assert dev.device_type == "handheld_console"
        assert dev.type_label == "Consola Portátil de Juegos"


def test_intermittent_intermediary_policies(app):
    """Verifica la configuración del intermediario con intermitencia y destinos web específicos."""
    with app.app_context():
        dev = create_device(
            {
                "name": "Tablet Estudio",
                "ip_address": "192.168.1.80",
                "network_scope": "192.168.1.0/24",
                "device_type": "tablet",
                "profile": "child",
            }
        )

        # Crear política de intermediario con ciclos de 45m ON / 15m OFF hacia un dominio específico
        policy = create_policy(
            {
                "name": "Control Intermitente YouTube",
                "device_id": dev.id,
                "policy_type": "intermittent_intermediary",
                "action": "restrict",
                "target_scope": "specific_domain",
                "target_domain": "youtube.com",
                "is_intermittent": True,
                "interval_active_minutes": 45,
                "interval_pause_minutes": 15,
                "valid_from": "2026-11-05 08:00",
                "status": "active",
            }
        )

        assert policy.id is not None
        assert policy.is_intermittent is True
        assert policy.interval_active_minutes == 45
        assert policy.interval_pause_minutes == 15
        assert policy.target_domain == "youtube.com"
        assert "45 min activo / 15 min pausa (youtube.com)" in policy.intermittent_summary

        # Comprobar que el simulador genera la directiva de intermediario esperada
        sync_res = execute_policy_router_sync(policy)
        assert "[SIMULADOR-INTERMEDIARIO]" in sync_res.command_preview
        assert "target=youtube.com" in sync_res.command_preview
        assert "cycle=45m_ON/15m_OFF" in sync_res.command_preview


def test_operator_friendly_family_access(app, client):
    """Comprueba que el rol Operador puede modular el acceso con un solo clic en lenguaje familiar."""
    with app.app_context():
        dev = create_device(
            {
                "name": "Smart TV Familiar",
                "ip_address": "192.168.1.90",
                "network_scope": "192.168.1.0/24",
                "device_type": "smart_tv",
                "profile": "family",
                "admin_status": "authorized",
            }
        )
        dev_id = dev.id

        # Crear un usuario con rol 'operator' (Operador del Hogar)
        create_user(
            username="papa_familia",
            email="papa@familia.local",
            full_name="Padre de Familia",
            password="FamiliaPassword123!",
            role="operator",
            is_active=True,
        )

    # Autenticar como operador
    login_page = client.get("/auth/login")
    csrf_token = extract_csrf_token(login_page.get_data(as_text=True))
    login_resp = client.post(
        "/auth/login",
        data={
            "csrf_token": csrf_token,
            "username": "papa_familia",
            "password": "FamiliaPassword123!",
        },
        follow_redirects=True,
    )
    assert login_resp.status_code == 200

    # 1. Aplicar "Pausa Temporal de Internet" (Comida / Dormir)
    detail_page = client.get(f"/devices/{dev_id}?tab=family")
    csrf_token_action = extract_csrf_token(detail_page.get_data(as_text=True))
    pause_resp = client.post(
        f"/devices/{dev_id}/family-access",
        data={
            "csrf_token": csrf_token_action,
            "mode": "pause",
        },
        follow_redirects=True,
    )
    assert pause_resp.status_code == 200
    html_resp = pause_resp.get_data(as_text=True)
    assert "Pausa Temporal de Internet" in html_resp

    with app.app_context():
        d = db.session.get(Device, dev_id)
        assert d.admin_status == "restricted"

    # 2. Habilitar "Internet Libre" con 1 clic
    csrf_token_action2 = extract_csrf_token(pause_resp.get_data(as_text=True))
    allow_resp = client.post(
        f"/devices/{dev_id}/family-access",
        data={
            "csrf_token": csrf_token_action2,
            "mode": "allow",
        },
        follow_redirects=True,
    )
    assert allow_resp.status_code == 200
    assert "Internet Libre" in allow_resp.get_data(as_text=True)

    with app.app_context():
        d = db.session.get(Device, dev_id)
        assert d.admin_status == "authorized"


def test_grouped_editor_in_device_detail(app, auth_client):
    """Comprueba que la edición agrupada dentro de la Ficha Técnica actualiza el dispositivo sin salir."""
    with app.app_context():
        dev = create_device(
            {
                "name": "Computadora de Prueba",
                "ip_address": "192.168.1.95",
                "network_scope": "192.168.1.0/24",
                "device_type": "workstation",
                "profile": "family",
            }
        )
        dev_id = dev.id

    detail_resp = auth_client.get(f"/devices/{dev_id}?tab=editor")
    assert detail_resp.status_code == 200
    html = detail_resp.get_data(as_text=True)
    assert "Editor de Parámetros de Red" in html
    csrf_token = extract_csrf_token(html)

    # Actualizar directamente enviando POST a la URL de la ficha técnica
    update_resp = auth_client.post(
        f"/devices/{dev_id}",
        data={
            "csrf_token": csrf_token,
            "name": "Computadora de Estudio Actualizada",
            "ip_address": "192.168.1.96",
            "network_scope": "192.168.1.0/24",
            "device_type": "laptop",
            "profile": "family",
            "admin_status": "authorized",
            "ip_assignment_type": "dhcp_reservation",
        },
        follow_redirects=True,
    )
    assert update_resp.status_code == 200
    resp_text = update_resp.get_data(as_text=True)
    assert "Computadora de Estudio Actualizada" in resp_text
    assert "192.168.1.96" in resp_text

    with app.app_context():
        updated_dev = db.session.get(Device, dev_id)
        assert updated_dev.name == "Computadora de Estudio Actualizada"
        assert updated_dev.ip_address == "192.168.1.96"
        assert updated_dev.device_type == "laptop"

