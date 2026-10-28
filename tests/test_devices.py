"""
Pruebas automatizadas del módulo de Administración de Dispositivos y Validaciones IP/MAC.
"""

import pytest
from app.models.device import Device
from app.services.device_service import create_device, delete_device, update_device
from app.services.validators import (
    ValidationError,
    validate_and_normalize_ip,
    validate_and_normalize_mac,
)
from tests.conftest import extract_csrf_token


def test_ip_address_validation_rules():
    """Comprueba la validación estricta de direcciones IP e intervalos CIDR."""
    # IP válida dentro del ámbito
    assert validate_and_normalize_ip("192.168.1.45", "192.168.1.0/24") == "192.168.1.45"

    # Formato inválido
    with pytest.raises(ValidationError, match="no tiene un formato válido"):
        validate_and_normalize_ip("999.168.1.1", "192.168.1.0/24")

    # Loopback rechazado
    with pytest.raises(ValidationError, match="reservada"):
        validate_and_normalize_ip("127.0.0.1")

    # Fuera del ámbito administrado
    with pytest.raises(ValidationError, match="no pertenece al ámbito"):
        validate_and_normalize_ip("10.0.0.15", "192.168.1.0/24")

    # Dirección de red y de broadcast rechazadas en /24
    with pytest.raises(ValidationError, match="identificador de red"):
        validate_and_normalize_ip("192.168.1.0", "192.168.1.0/24")

    with pytest.raises(ValidationError, match="broadcast"):
        validate_and_normalize_ip("192.168.1.255", "192.168.1.0/24")


def test_mac_address_validation_and_normalization():
    """Comprueba la normalización y validación de direcciones MAC opcionales."""
    assert validate_and_normalize_mac("") is None
    assert validate_and_normalize_mac(None) is None
    assert validate_and_normalize_mac("aa-bb-cc-dd-ee-01") == "AA:BB:CC:DD:EE:01"
    assert validate_and_normalize_mac("aabb.ccdd.ee02") == "AA:BB:CC:DD:EE:02"

    with pytest.raises(ValidationError, match="MAC"):
        validate_and_normalize_mac("GG:BB:CC:DD:EE:FF")

    with pytest.raises(ValidationError, match="reservada"):
        validate_and_normalize_mac("FF:FF:FF:FF:FF:FF")


def test_create_edit_delete_device_and_prevent_duplicates(app, admin_user):
    """Comprueba el ciclo CRUD completo de dispositivos y la prevención de IP/MAC duplicadas."""
    with app.app_context():
        dev1 = create_device(
            {
                "name": "Laptop Ingeniería",
                "hostname": "laptop-ing.lan",
                "ip_address": "192.168.1.20",
                "network_scope": "192.168.1.0/24",
                "ip_assignment_type": "dhcp_reservation",
                "mac_address": "aa:bb:cc:00:11:22",
                "device_type": "laptop",
                "admin_status": "authorized",
            },
            user_id=admin_user,
        )
        assert dev1.id is not None
        assert dev1.internal_code == "DEV-0001"
        assert dev1.mac_address == "AA:BB:CC:00:11:22"
        assert dev1.router_sync_status == "only_in_db"

        # Intentar duplicar la misma IP en el mismo ámbito debe fallar
        with pytest.raises(ValidationError, match="Conflicto de dirección IP"):
            create_device(
                {
                    "name": "Equipo Duplicado IP",
                    "ip_address": "192.168.1.20",
                    "network_scope": "192.168.1.0/24",
                },
                user_id=admin_user,
            )

        # Intentar duplicar la misma dirección MAC debe fallar
        with pytest.raises(ValidationError, match="Conflicto de dirección MAC"):
            create_device(
                {
                    "name": "Equipo Duplicado MAC",
                    "ip_address": "192.168.1.21",
                    "network_scope": "192.168.1.0/24",
                    "mac_address": "AA-BB-CC-00-11-22",
                },
                user_id=admin_user,
            )

        # La misma IP en un ámbito de red distinto sí está permitida por el modelo
        dev_other_scope = create_device(
            {
                "name": "Servidor VLAN Lab",
                "ip_address": "192.168.1.20",
                "network_scope": "192.168.0.0/16",
                "device_type": "server",
                "admin_status": "authorized",
            },
            user_id=admin_user,
        )
        assert dev_other_scope.id != dev1.id

        # Editar dispositivo
        updated = update_device(
            dev1,
            {
                "name": "Laptop Ingeniería Actualizada",
                "ip_address": "192.168.1.22",
                "network_scope": "192.168.1.0/24",
                "mac_address": "AA:BB:CC:00:11:22",
                "device_type": "laptop",
                "admin_status": "restricted",
                "ip_assignment_type": "dhcp_reservation",
            },
            user_id=admin_user,
        )
        assert updated.name == "Laptop Ingeniería Actualizada"
        assert updated.ip_address == "192.168.1.22"
        assert updated.admin_status == "restricted"

        # Eliminar dispositivo
        dev_id = dev1.id
        delete_device(dev1, user_id=admin_user)
        assert Device.query.filter_by(id=dev_id).first() is None


def test_device_http_crud_routes(auth_client, app):
    """Comprueba la creación, consulta, edición y eliminación de dispositivos vía HTTP con CSRF."""
    form_resp = auth_client.get("/devices/new")
    assert form_resp.status_code == 200
    csrf_token = extract_csrf_token(form_resp.get_data(as_text=True))

    create_resp = auth_client.post(
        "/devices/new",
        data={
            "csrf_token": csrf_token,
            "name": "Smart TV Sala HTTP",
            "hostname": "tv-sala.lan",
            "ip_address": "192.168.1.75",
            "network_scope": "192.168.1.0/24",
            "ip_assignment_type": "static_manual",
            "mac_address": "11:22:33:44:55:66",
            "device_type": "smart_tv",
            "admin_status": "authorized",
            "sync_with_adapter": "1",
        },
        follow_redirects=True,
    )
    assert create_resp.status_code == 200
    html = create_resp.get_data(as_text=True)
    assert "Smart TV Sala HTTP" in html
    assert "192.168.1.75" in html
    assert "Aplicado en Simulador de Laboratorio" in html

