"""
Pruebas automatizadas de Auditoría, Redacción de Secretos, Adaptador de Router
y Manejo Controlado de Errores de Base de Datos.
"""

import pytest
from sqlalchemy.exc import OperationalError
from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import utc_now_naive
from app.services.audit_service import log_audit_event
from app.services.dashboard_service import get_dashboard_metrics
from app.services.device_service import create_device
from app.services.policy_service import create_policy
from app.services.router_adapter import execute_device_router_sync, execute_policy_router_sync
from app.services.validators import ValidationError


def test_audit_log_redacts_sensitive_secrets(app, admin_user):
    """Comprueba que nunca se almacenen contraseñas, hashes ni tokens en la bitácora."""
    with app.app_context():
        entry = log_audit_event(
            event_type="SECURITY_TEST_EVENT",
            module="system",
            description="Prueba de sanitización de metadatos sensibles.",
            severity="security",
            user_id=admin_user,
            metadata={
                "username": "admin_test",
                "password": "MiPasswordEnTextoPlano123",
                "password_hash": "scrypt:32768:8:1$...",
                "csrf_token": "token_secreto_12345",
                "session_cookie": "cookie_privada_xyz",
                "safe_field": "valor_permitido",
            },
            commit=True,
        )

        meta = entry.metadata_dict
        assert meta["username"] == "admin_test"
        assert meta["safe_field"] == "valor_permitido"
        assert meta["password"] == "[REDACTED]"
        assert meta["password_hash"] == "[REDACTED]"
        assert meta["csrf_token"] == "[REDACTED]"
        assert meta["session_cookie"] == "[REDACTED]"
        assert "MiPasswordEnTextoPlano123" not in (entry.metadata_json or "")


def test_audit_history_is_read_only_from_web_interface(auth_client):
    """Comprueba que la interfaz de auditoría solo permite consulta y rechaza modificaciones."""
    get_resp = auth_client.get("/audit/")
    assert get_resp.status_code == 200

    post_resp = auth_client.post("/audit/", data={"action": "delete_all"})
    assert post_resp.status_code == 405

    delete_resp = auth_client.delete("/audit/")
    assert delete_resp.status_code == 405


def test_database_error_handling_and_rollback(app, admin_user, monkeypatch):
    """Comprueba que un fallo del motor de base de datos revierte la sesión sin cerrar la app."""
    with app.app_context():
        original_flush = db.session.flush

        def simulated_db_failure(*args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("Simulated DB connection drop"))

        monkeypatch.setattr(db.session, "flush", simulated_db_failure)

        with pytest.raises(ValidationError, match="Error interno de base de datos"):
            create_device(
                {
                    "name": "Dispositivo Con Fallo DB",
                    "ip_address": "192.168.1.111",
                    "network_scope": "192.168.1.0/24",
                },
                user_id=admin_user,
            )

        # Restaurar flush normal y verificar que la sesión sigue operativa tras el rollback
        monkeypatch.setattr(db.session, "flush", original_flush)
        error_log = AuditLog.query.filter_by(event_type="DEVICE_CREATE_ERROR").first()
        assert error_log is not None
        assert error_log.severity == "error"


def test_router_adapter_three_layer_separation_and_dashboard_metrics(app, admin_user):
    """
    Comprueba la separación entre:
    1) Registro en BD (`only_in_db` / `stored_in_db`),
    2) Sincronización en Simulador de Laboratorio (`simulated_applied` / `simulated_in_lab`),
    3) Modo Pasivo (`only_in_db` / `stored_in_db`),
    y verifica que el Dashboard refleje las cifras exactas de la base de datos.
    """
    with app.app_context():
        dev = create_device(
            {
                "name": "Impresora Red Oficina",
                "ip_address": "192.168.1.200",
                "network_scope": "192.168.1.0/24",
                "mac_address": "00:11:22:33:44:55",
                "device_type": "printer",
                "admin_status": "authorized",
            },
            user_id=admin_user,
        )
        pol = create_policy(
            {
                "name": "Autorización Impresora LAN",
                "device_id": dev.id,
                "policy_type": "permanent_access",
                "action": "allow",
                "priority": 10,
                "valid_from": utc_now_naive(),
            },
            user_id=admin_user,
        )

        # Recién creados: únicamente existen en la base de datos
        assert dev.router_sync_status == "only_in_db"
        assert pol.enforcement_status == "stored_in_db"

        # Sincronizar en modo Simulador de Laboratorio
        app.config["ROUTER_ADAPTER_MODE"] = "lab_simulator"
        dev_res = execute_device_router_sync(dev, triggered_by_id=admin_user)
        pol_res = execute_policy_router_sync(pol, triggered_by_id=admin_user)

        assert dev_res.is_simulated is True
        assert dev.router_sync_status == "simulated_applied"
        assert pol_res.is_simulated is True
        assert pol.enforcement_status == "simulated_in_lab"

        # Cambiar a modo Pasivo (sin simulador) y verificar que se reporta como solo en BD
        app.config["ROUTER_ADAPTER_MODE"] = "passive_only"
        passive_res = execute_device_router_sync(dev, triggered_by_id=admin_user)
        assert passive_res.is_simulated is False
        assert dev.router_sync_status == "only_in_db"

        # Verificar métricas reales del Dashboard
        metrics = get_dashboard_metrics()
        assert metrics["total_devices"] == 1
        assert metrics["authorized_devices"] == 1
        assert metrics["active_policies_count"] == 1

