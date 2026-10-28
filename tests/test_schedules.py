"""
Pruebas automatizadas del módulo de Horarios de Acceso y Cruce de Medianoche.
"""

from datetime import datetime
import pytest
from app.services.device_service import create_device
from app.services.schedule_service import (
    create_schedule,
    delete_schedule,
    toggle_schedule_active,
)
from app.services.validators import ValidationError


def test_schedule_validation_and_midnight_crossing_evaluation(app, admin_user):
    """Comprueba horarios diurnos, horarios que cruzan la medianoche y validaciones de formato."""
    with app.app_context():
        dev = create_device(
            {
                "name": "Consola Sala",
                "ip_address": "192.168.1.90",
                "network_scope": "192.168.1.0/24",
                "device_type": "console",
                "admin_status": "restricted",
            },
            user_id=admin_user,
        )

        # Hora inicial igual a hora final -> debe fallar
        with pytest.raises(ValidationError, match="no pueden ser idénticas"):
            create_schedule(
                {
                    "label": "Horario Nulo",
                    "device_id": dev.id,
                    "days_of_week": [0, 1],
                    "start_time": "14:00",
                    "end_time": "14:00",
                },
                user_id=admin_user,
            )

        # Sin días seleccionados -> debe fallar
        with pytest.raises(ValidationError, match="al menos un día"):
            create_schedule(
                {
                    "label": "Sin Días",
                    "device_id": dev.id,
                    "days_of_week": [],
                    "start_time": "14:00",
                    "end_time": "18:00",
                },
                user_id=admin_user,
            )

        # 1. Horario diurno: Lunes (0) y Miércoles (2) de 16:00 a 20:00
        sch_day = create_schedule(
            {
                "label": "Tarde Videojuegos",
                "device_id": dev.id,
                "days_of_week": [0, 2],
                "start_time": "16:00",
                "end_time": "20:00",
                "window_behavior": "allowed_window",
                "is_active": True,
            },
            user_id=admin_user,
        )
        assert sch_day.crosses_midnight is False

        # Lunes 2026-10-26 17:30 (weekday == 0) -> dentro de ventana
        assert sch_day.is_in_window_at(datetime(2026, 10, 26, 17, 30)) is True
        # Lunes 2026-10-26 21:00 -> fuera de ventana
        assert sch_day.is_in_window_at(datetime(2026, 10, 26, 21, 0)) is False
        # Martes 2026-10-27 17:30 (weekday == 1) -> fuera de ventana
        assert sch_day.is_in_window_at(datetime(2026, 10, 27, 17, 30)) is False

        # 2. Horario que cruza la medianoche: Lunes (0) de 22:00 a 06:00 (termina Martes a las 06:00)
        sch_night = create_schedule(
            {
                "label": "Restricción Nocturna Lunes a Martes",
                "device_id": dev.id,
                "days_of_week": [0],  # Solo inicia los Lunes por la noche
                "start_time": "22:00",
                "end_time": "06:00",
                "window_behavior": "restricted_window",
                "is_active": True,
            },
            user_id=admin_user,
        )
        assert sch_night.crosses_midnight is True

        # Lunes 2026-10-26 23:15 -> tramo nocturno del Lunes: ACTIVO
        assert sch_night.is_in_window_at(datetime(2026, 10, 26, 23, 15)) is True
        # Martes 2026-10-27 03:30 -> tramo de madrugada iniciado el Lunes: ACTIVO
        assert sch_night.is_in_window_at(datetime(2026, 10, 27, 3, 30)) is True
        # Martes 2026-10-27 07:00 -> ya terminó la ventana: INACTIVO
        assert sch_night.is_in_window_at(datetime(2026, 10, 27, 7, 0)) is False
        # Martes 2026-10-27 23:15 -> Martes no está en days_of_week: INACTIVO
        assert sch_night.is_in_window_at(datetime(2026, 10, 27, 23, 15)) is False

        # Próximas ventanas calculadas
        windows = sch_night.get_upcoming_windows(
            reference_dt=datetime(2026, 10, 26, 21, 0),
            max_windows=2,
        )
        assert len(windows) == 2
        assert windows[0][0] == datetime(2026, 10, 26, 22, 0)
        assert windows[0][1] == datetime(2026, 10, 27, 6, 0)

        # Pausar horario -> ya no evalúa activo
        toggle_schedule_active(sch_night, user_id=admin_user)
        assert sch_night.is_active is False
        assert sch_night.is_in_window_at(datetime(2026, 10, 26, 23, 15)) is False

        delete_schedule(sch_night, user_id=admin_user)
        delete_schedule(sch_day, user_id=admin_user)

