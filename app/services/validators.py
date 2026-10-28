"""
Validadores de dominio para direcciones IP, subredes CIDR, direcciones MAC,
intervalos temporales de políticas y ventanas horarias.
"""

import ipaddress
import re
from datetime import datetime, time
from typing import Iterable, Optional, Tuple


class ValidationError(ValueError):
    """Error de validación de reglas de negocio con mensaje seguro para el usuario."""


MAC_HEX_RE = re.compile(r"^[0-9A-F]{12}$")
HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9\-]+)*$")
TIME_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def validate_network_scope(scope_str: str) -> str:
    """Valida una subred en notación CIDR (ej. 192.168.1.0/24) y devuelve su forma canónica."""
    raw = (scope_str or "").strip()
    if not raw:
        raise ValidationError("El ámbito de red (subred CIDR) es obligatorio.")
    try:
        net = ipaddress.ip_network(raw, strict=False)
    except ValueError as exc:
        raise ValidationError(
            f"El ámbito de red '{raw}' no es una subred CIDR válida (ejemplo: 192.168.1.0/24)."
        ) from exc

    if net.is_multicast or net.is_loopback or net.is_unspecified:
        raise ValidationError("El ámbito de red no puede ser loopback, multicast ni no especificado.")

    return str(net)


def validate_and_normalize_ip(
    ip_str: str,
    network_scope: Optional[str] = None,
) -> str:
    """
    Valida una dirección IPv4/IPv6 usando la biblioteca estándar `ipaddress`.
    Si se indica `network_scope`, comprueba que la dirección pertenezca a la subred
    y que no corresponda a la dirección de red ni de broadcast.
    """
    raw = (ip_str or "").strip()
    if not raw:
        raise ValidationError("La dirección IP es obligatoria.")

    try:
        ip_obj = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise ValidationError(f"La dirección IP '{raw}' no tiene un formato válido.") from exc

    if ip_obj.is_unspecified or ip_obj.is_loopback or ip_obj.is_multicast:
        raise ValidationError(
            f"La dirección IP '{ip_obj}' es reservada (loopback, multicast o no especificada) "
            "y no puede asignarse a un dispositivo de red doméstica."
        )

    if network_scope:
        canonical_scope = validate_network_scope(network_scope)
        net = ipaddress.ip_network(canonical_scope, strict=False)
        if ip_obj.version != net.version:
            raise ValidationError(
                f"La dirección IP '{ip_obj}' no coincide con la versión IP del ámbito '{canonical_scope}'."
            )
        if ip_obj not in net:
            raise ValidationError(
                f"La dirección IP '{ip_obj}' no pertenece al ámbito de red administrado '{canonical_scope}'."
            )
        if isinstance(net, ipaddress.IPv4Network) and net.prefixlen <= 30:
            if ip_obj == net.network_address:
                raise ValidationError(
                    f"La dirección '{ip_obj}' es el identificador de red de '{canonical_scope}' "
                    "y no puede asignarse a un host."
                )
            if ip_obj == net.broadcast_address:
                raise ValidationError(
                    f"La dirección '{ip_obj}' es la dirección de broadcast de '{canonical_scope}' "
                    "y no puede asignarse a un host."
                )

    return str(ip_obj)


def validate_and_normalize_mac(mac_str: Optional[str]) -> Optional[str]:
    """
    Valida y normaliza una dirección física MAC opcional al formato canónico AA:BB:CC:DD:EE:FF.
    Si no se proporciona (cadena vacía o None), devuelve None.
    """
    if mac_str is None:
        return None
    raw = mac_str.strip()
    if not raw:
        return None

    # Eliminar separadores habituales (:, -, .)
    cleaned = re.sub(r"[:\-\.]", "", raw).upper()
    if not MAC_HEX_RE.match(cleaned):
        raise ValidationError(
            f"La dirección MAC '{raw}' no es válida. Use el formato hexadecimal AA:BB:CC:DD:EE:FF."
        )

    normalized = ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))
    if normalized in ("00:00:00:00:00:00", "FF:FF:FF:FF:FF:FF"):
        raise ValidationError(
            f"La dirección MAC '{normalized}' es reservada (nula o broadcast) y no identifica un dispositivo válido."
        )
    return normalized


def validate_hostname(hostname: Optional[str]) -> Optional[str]:
    """Valida el nombre de host de red cuando se proporciona."""
    if hostname is None:
        return None
    cleaned = hostname.strip()
    if not cleaned:
        return None
    if len(cleaned) > 100 or not HOSTNAME_RE.match(cleaned):
        raise ValidationError(
            f"El nombre de host '{cleaned}' contiene caracteres no válidos. "
            "Use letras, números, guiones y puntos sin espacios."
        )
    return cleaned


def validate_policy_temporal_rules(
    policy_type: str,
    action: str,
    valid_from: Optional[datetime],
    valid_until: Optional[datetime],
    navigation_profile: Optional[str] = None,
) -> None:
    """
    Valida la coherencia temporal y semántica de una política de acceso:
    - `valid_from` es obligatorio.
    - Si existe `valid_until`, debe ser estrictamente posterior a `valid_from`.
    - Las políticas de `temporary_access` requieren obligatoriamente `valid_until`.
    - Las políticas de `permanent_access` no deben incluir fecha de finalización.
    - Las políticas de `navigation_restriction` no pueden tener acción `allow` sin filtro.
    """
    valid_types = (
        "administrative_auth",
        "temporary_access",
        "allowed_schedule",
        "navigation_restriction",
        "permanent_access",
    )
    if policy_type not in valid_types:
        raise ValidationError(f"Tipo de política inválido: '{policy_type}'.")

    if action not in ("allow", "restrict", "block"):
        raise ValidationError(f"Acción de política inválida: '{action}'.")

    if valid_from is None:
        raise ValidationError("La fecha y hora de inicio de la política es obligatoria.")

    if valid_until is not None and valid_until <= valid_from:
        raise ValidationError(
            "El intervalo temporal es inválido: la fecha de finalización debe ser posterior a la fecha de inicio."
        )

    if policy_type == "temporary_access" and valid_until is None:
        raise ValidationError(
            "Una política de 'Acceso Temporal' requiere obligatoriamente una fecha y hora de finalización."
        )

    if policy_type == "permanent_access" and valid_until is not None:
        raise ValidationError(
            "Contradicción detectada: una 'Política de Acceso Permanente' no debe tener fecha de finalización."
        )

    if policy_type == "navigation_restriction":
        if action == "allow":
            raise ValidationError(
                "Contradicción detectada: una política de 'Restricciones de Navegación' debe tener "
                "acción 'Restringir / Filtrar' o 'Bloquear Tráfico', no 'Permitir Acceso'."
            )
        if not (navigation_profile or "").strip():
            raise ValidationError(
                "Para 'Restricciones de Navegación Configurables', especifique los criterios o perfil "
                "de restricción (ej. bloqueo DNS de categorías o puertos restringidos)."
            )


def validate_schedule_params(
    days_input: Iterable[str | int],
    start_time_str: str,
    end_time_str: str,
    window_behavior: str = "allowed_window",
) -> Tuple[str, str, str, bool]:
    """
    Valida los días de la semana y las horas de inicio/fin de un horario de acceso.
    Devuelve: `(days_csv, start_hhmm, end_hhmm, crosses_midnight)`.
    """
    if window_behavior not in ("allowed_window", "restricted_window"):
        raise ValidationError("El tipo de comportamiento del horario no es válido.")

    parsed_days = set()
    for d in days_input or []:
        s = str(d).strip()
        if not s:
            continue
        if not s.isdigit() or not (0 <= int(s) <= 6):
            raise ValidationError(f"Día de la semana inválido: '{s}'. Use valores de 0 (Lunes) a 6 (Domingo).")
        parsed_days.add(int(s))

    if not parsed_days:
        raise ValidationError("Debe seleccionar al menos un día de la semana para el horario.")

    start_clean = (start_time_str or "").strip()
    end_clean = (end_time_str or "").strip()

    if not TIME_HHMM_RE.match(start_clean):
        raise ValidationError(f"Hora inicial inválida '{start_clean}'. Utilice el formato de 24 horas HH:MM.")
    if not TIME_HHMM_RE.match(end_clean):
        raise ValidationError(f"Hora final inválida '{end_clean}'. Utilice el formato de 24 horas HH:MM.")

    if start_clean == end_clean:
        raise ValidationError(
            "La hora inicial y la hora final no pueden ser idénticas. Defina un intervalo de al menos 1 minuto."
        )

    sh, sm = map(int, start_clean.split(":"))
    eh, em = map(int, end_clean.split(":"))
    t_start = time(sh, sm)
    t_end = time(eh, em)

    crosses_midnight = t_start > t_end
    days_csv = ",".join(str(d) for d in sorted(parsed_days))
    return days_csv, start_clean, end_clean, crosses_midnight

