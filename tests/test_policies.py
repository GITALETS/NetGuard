"""
Pruebas automatizadas del módulo de Políticas de Acceso, Validaciones Temporales y Cálculo de Vigencia.
"""

from datetime import timedelta
import pytest
from app.models.policy import AccessPolicy
from app.models.user import utc_now_naive
from app.services.device_service import create_device
from app.services.policy_service import (
    create_policy,
    delete_policy,
    refresh_expired_policies,
    update_policy,
)
from app.services.validators import ValidationError


def test_policy_creation_categories_and_temporal_validations(app, admin_user):
    """Comprueba la creación de políticas, validación de fechas y contradicciones por categoría."""
    with app.app_context():
        now = utc_now_naive()
        dev = create_device(
            {
                "name": "PC Pruebas Políticas",
                "ip_address": "192.168.1.30",
                "network_scope": "192.168.1.0/24",
                "device_type": "workstation",
                "admin_status": "authorized",
            },
            user_id=admin_user,
        )

        # 1. Fecha final anterior o igual a inicial -> debe fallar
        with pytest.raises(ValidationError, match="intervalo temporal es inválido"):
            create_policy(
                {
                    "name": "Política Fechas Invertidas",
                    "device_id": dev.id,
                    "policy_type": "temporary_access",
                    "action": "allow",
                    "valid_from": now,
                    "valid_until": now - timedelta(hours=2),
                },
                user_id=admin_user,
            )

        # 2. Acceso temporal sin fecha final -> debe fallar
        with pytest.raises(ValidationError, match="Acceso Temporal"):
            create_policy(
                {
                    "name": "Temporal Sin Fin",
                    "device_id": dev.id,
                    "policy_type": "temporary_access",
                    "action": "allow",
                    "valid_from": now,
                    "valid_until": None,
                },
                user_id=admin_user,
            )

        # 3. Acceso permanente con fecha de expiración -> contradicción, debe fallar
        with pytest.raises(ValidationError, match="Contradicción detectada"):
            create_policy(
                {
                    "name": "Permanente Contradictoria",
                    "device_id": dev.id,
                    "policy_type": "permanent_access",
                    "action": "allow",
                    "valid_from": now,
                    "valid_until": now + timedelta(days=5),
                },
                user_id=admin_user,
            )

        # 4. Restricción de navegación con acción 'allow' -> contradicción, debe fallar
        with pytest.raises(ValidationError, match="Restricciones de Navegación"):
            create_policy(
                {
                    "name": "Navegación Contradictoria",
                    "device_id": dev.id,
                    "policy_type": "navigation_restriction",
                    "action": "allow",
                    "valid_from": now,
                },
                user_id=admin_user,
            )

        # 5. Crear política permanente válida
        pol_perm = create_policy(
            {
                "name": "Acceso Permanente PC",
                "device_id": dev.id,
                "policy_type": "permanent_access",
                "action": "allow",
                "priority": 10,
                "valid_from": now - timedelta(hours=1),
                "valid_until": None,
            },
            user_id=admin_user,
        )
        assert pol_perm.is_currently_effective(now) is True
        assert pol_perm.enforcement_status == "stored_in_db"

        # 6. Intentar crear una política activa opuesta ('block') con la misma prioridad (10)
        # y solapamiento temporal en el mismo dispositivo -> debe rechazarse
        with pytest.raises(ValidationError, match="Combinación contradictoria detectada"):
            create_policy(
                {
                    "name": "Bloqueo Contradictorio Misma Prioridad",
                    "device_id": dev.id,
                    "policy_type": "administrative_auth",
                    "action": "block",
                    "priority": 10,
                    "valid_from": now,
                },
                user_id=admin_user,
            )


def test_active_vs_expired_and_scheduled_policy_calculation(app, admin_user):
    """Comprueba que las políticas expiradas nunca se evalúan ni muestran como vigentes."""
    with app.app_context():
        now = utc_now_naive()
        dev = create_device(
            {
                "name": "Tableta Vigencias",
                "ip_address": "192.168.1.35",
                "network_scope": "192.168.1.0/24",
                "device_type": "tablet",
                "admin_status": "restricted",
            },
            user_id=admin_user,
        )

        # Política vigente actualmente
        pol_active = create_policy(
            {
                "name": "Acceso Temporal Vigente",
                "device_id": dev.id,
                "policy_type": "temporary_access",
                "action": "allow",
                "priority": 20,
                "valid_from": now - timedelta(hours=2),
                "valid_until": now + timedelta(hours=2),
            },
            user_id=admin_user,
        )
        assert pol_active.is_currently_effective(now) is True
        assert pol_active.effective_status_at(now) == "active"

        # Evaluada 3 horas en el futuro -> debe reportarse como 'expired' y NO vigente
        future_time = now + timedelta(hours=3)
        assert pol_active.is_currently_effective(future_time) is False
        assert pol_active.effective_status_at(future_time) == "expired"

        # Política futura (programada para iniciar mañana)
        pol_future = create_policy(
            {
                "name": "Acceso Programado Mañana",
                "device_id": dev.id,
                "policy_type": "temporary_access",
                "action": "allow",
                "priority": 30,
                "valid_from": now + timedelta(days=1),
                "valid_until": now + timedelta(days=2),
            },
            user_id=admin_user,
        )
        assert pol_future.is_currently_effective(now) is False
        assert pol_future.effective_status_at(now) == "scheduled"

        # Actualizar estado en BD al avanzar el reloj de referencia
        updated_count = refresh_expired_policies(reference_time=future_time)
        assert updated_count == 1
        assert pol_active.status == "expired"

        # Modificar y eliminar política
        update_policy(
            pol_future,
            {
                "name": "Acceso Programado Editado",
                "device_id": dev.id,
                "policy_type": "temporary_access",
                "action": "restrict",
                "priority": 35,
                "status": "paused",
                "valid_from": now + timedelta(days=1),
                "valid_until": now + timedelta(days=3),
            },
            user_id=admin_user,
        )
        assert pol_future.status == "paused"
        assert pol_future.is_currently_effective(now + timedelta(days=1, hours=2)) is False

        pol_id = pol_future.id
        delete_policy(pol_future, user_id=admin_user)
        assert AccessPolicy.query.filter_by(id=pol_id).first() is None

