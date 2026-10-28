"""
Modelo de Horarios de Acceso (AccessSchedule).
Implementa evaluación determinista de ventanas horarias tanto diurnas como
nocturnas que cruzan la medianoche (ej. 22:00 -> 06:00 del día siguiente).
"""

from datetime import datetime, time, timedelta
from typing import List, Optional, Set, Tuple
from app.extensions import db
from app.models.user import utc_now_naive


class AccessSchedule(db.Model):
    """Representa una programación horaria asociada a un dispositivo y/o política."""

    __tablename__ = "access_schedules"

    DAY_NAMES = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo",
    }
    DAY_SHORT_NAMES = {
        0: "Lun",
        1: "Mar",
        2: "Mié",
        3: "Jue",
        4: "Vie",
        5: "Sáb",
        6: "Dom",
    }

    VALID_BEHAVIORS = ("allowed_window", "restricted_window")
    BEHAVIOR_LABELS = {
        "allowed_window": "Ventana de Acceso Permitido",
        "restricted_window": "Ventana de Restricción / Bloqueo",
    }

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    device_id = db.Column(
        db.Integer,
        db.ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id = db.Column(
        db.Integer,
        db.ForeignKey("access_policies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    days_of_week = db.Column(db.String(32), nullable=False)  # Ej: "0,1,2,3,4"
    start_time = db.Column(db.String(5), nullable=False)  # Formato HH:MM
    end_time = db.Column(db.String(5), nullable=False)  # Formato HH:MM
    window_behavior = db.Column(
        db.String(24),
        nullable=False,
        default="allowed_window",
    )
    crosses_midnight = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    enforcement_note = db.Column(db.String(255), nullable=True)
    is_demo = db.Column(db.Boolean, nullable=False, default=False)
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now_naive,
        onupdate=utc_now_naive,
    )

    device = db.relationship("Device", back_populates="schedules")
    policy = db.relationship("AccessPolicy", back_populates="schedules")
    created_by = db.relationship("User", backref=db.backref("created_schedules", lazy="dynamic"))

    @staticmethod
    def parse_hhmm(value: str) -> time:
        """Convierte una cadena 'HH:MM' en un objeto datetime.time validado."""
        parts = (value or "").strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Formato de hora inválido: '{value}'. Use HH:MM.")
        hour, minute = int(parts[0]), int(parts[1])
        return time(hour=hour, minute=minute)

    @property
    def days_set(self) -> Set[int]:
        """Devuelve el conjunto de índices de día (0=Lunes ... 6=Domingo)."""
        result: Set[int] = set()
        if not self.days_of_week:
            return result
        for token in self.days_of_week.split(","):
            token = token.strip()
            if token.isdigit():
                day_idx = int(token)
                if 0 <= day_idx <= 6:
                    result.add(day_idx)
        return result

    @property
    def days_list_sorted(self) -> List[int]:
        return sorted(self.days_set)

    @property
    def days_human_label(self) -> str:
        days = self.days_list_sorted
        if not days:
            return "Sin días seleccionados"
        if days == [0, 1, 2, 3, 4, 5, 6]:
            return "Todos los días (Lun–Dom)"
        if days == [0, 1, 2, 3, 4]:
            return "Lunes a Viernes"
        if days == [5, 6]:
            return "Fines de semana (Sáb–Dom)"
        return ", ".join(self.DAY_SHORT_NAMES[d] for d in days)

    @property
    def behavior_label(self) -> str:
        return self.BEHAVIOR_LABELS.get(self.window_behavior, self.window_behavior)

    def is_in_window_at(self, reference_dt: Optional[datetime] = None) -> bool:
        """
        Determina si el instante `reference_dt` se encuentra dentro de la ventana
        programada y si el horario está activo.
        Soporta horarios que cruzan la medianoche (start_time > end_time):
        - Si start_time < end_time: evalúa si el día actual está en days_set y start <= t < end.
        - Si start_time > end_time (cruza medianoche):
            * Si t >= start_time: el tramo pertenece a la noche del día actual `weekday`.
            * Si t < end_time: el tramo pertenece a la madrugada iniciada el día anterior `(weekday - 1) % 7`.
        """
        if not self.is_active:
            return False

        days = self.days_set
        if not days:
            return False

        dt = reference_dt or datetime.now()
        t_start = self.parse_hhmm(self.start_time)
        t_end = self.parse_hhmm(self.end_time)
        current_t = time(hour=dt.hour, minute=dt.minute, second=dt.second)
        weekday = dt.weekday()

        if t_start < t_end:
            return (weekday in days) and (t_start <= current_t < t_end)
        elif t_start > t_end:
            # Cruza medianoche
            if current_t >= t_start:
                return weekday in days
            if current_t < t_end:
                prev_weekday = (weekday - 1) % 7
                return prev_weekday in days
            return False
        return False

    def get_upcoming_windows(
        self,
        reference_dt: Optional[datetime] = None,
        max_windows: int = 3,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Calcula las próximas `max_windows` ventanas de tiempo (inicio, fin)
        a partir de `reference_dt` (incluyendo la ventana en curso si está activa).
        """
        if not self.is_active or not self.days_set:
            return []

        dt = (reference_dt or datetime.now()).replace(second=0, microsecond=0)
        t_start = self.parse_hhmm(self.start_time)
        t_end = self.parse_hhmm(self.end_time)
        days = self.days_set
        windows: List[Tuple[datetime, datetime]] = []

        # Exploramos desde ayer (para capturar ventanas que cruzaron la medianoche hacia hoy)
        # hasta los próximos 14 días.
        base_date = dt.date() - timedelta(days=1)
        for offset in range(16):
            candidate_date = base_date + timedelta(days=offset)
            if candidate_date.weekday() not in days:
                continue

            win_start = datetime.combine(candidate_date, t_start)
            if t_start < t_end:
                win_end = datetime.combine(candidate_date, t_end)
            else:
                win_end = datetime.combine(candidate_date + timedelta(days=1), t_end)

            # Incluir si la ventana aún no ha terminado
            if win_end > dt:
                windows.append((win_start, win_end))
                if len(windows) >= max_windows:
                    break

        return windows

    def __repr__(self) -> str:
        return f"<AccessSchedule {self.id} {self.label} ({self.start_time}-{self.end_time})>"

