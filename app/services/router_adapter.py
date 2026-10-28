"""
Arquitectura de Adaptador de Integración con el Router (Patrón Adapter).

Separa explícitamente tres capas:
1. Administración de registros y políticas dentro de la base de datos de la aplicación.
2. Comunicación con el dispositivo de borde / router mediante la interfaz `RouterAdapterBase`.
3. Confirmación verificable de si la acción fue aplicada realmente, simulada en laboratorio
   o únicamente almacenada en la base de datos.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from flask import current_app
from app.extensions import db
from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.router_event import RouterSyncLog
from app.models.user import utc_now_naive
from app.services.audit_service import log_audit_event


@dataclass
class AdapterSyncResult:
    """Resultado estructurado de una operación solicitada al adaptador de red."""

    adapter_name: str
    operation: str
    is_simulated: bool
    result_status: str  # simulated_ok | applied_verified | not_applied_passive | failed
    device_sync_status: str  # only_in_db | simulated_applied | applied_confirmed | not_supported | sync_error
    policy_enforcement_status: str  # stored_in_db | simulated_in_lab | applied_in_router | unsupported_by_router | sync_error
    command_preview: str
    response_detail: str


class RouterAdapterBase(ABC):
    """
    Contrato abstracto que debe implementar cualquier conector hacia un router real
    (por ejemplo: OpenWrt ubus/UCI, MikroTik RouterOS API, OPNsense REST API)
    o el simulador de laboratorio.
    """

    adapter_id: str = "base"
    display_name: str = "Adaptador Base"
    is_simulated: bool = True
    supports_real_enforcement: bool = False

    @abstractmethod
    def get_diagnostics(self) -> Dict[str, Any]:
        """Devuelve el estado y capacidades técnicas del adaptador."""

    @abstractmethod
    def sync_device_state(self, device: Device) -> AdapterSyncResult:
        """Sincroniza el registro IP/MAC y estado administrativo de un dispositivo."""

    @abstractmethod
    def sync_policy_rule(self, policy: AccessPolicy) -> AdapterSyncResult:
        """Traduce y envía una política de acceso hacia el adaptador."""


class LabSimulatorRouterAdapter(RouterAdapterBase):
    """
    Adaptador Simulado de Laboratorio para demostración académica.
    NO modifica ninguna red real ni afirma bloquear tráfico real.
    Genera la previsualización técnica de las directivas que un gateway compatible
    recibiría y marca el estado como `simulated_applied` / `simulated_in_lab`.
    """

    adapter_id = "lab_simulator"
    display_name = "Simulador de Router Doméstico (Modo Laboratorio)"
    is_simulated = True
    supports_real_enforcement = False

    def get_diagnostics(self) -> Dict[str, Any]:
        gateway_ip = current_app.config.get("DEFAULT_GATEWAY_IP", "192.168.1.1")
        scope = current_app.config.get("DEFAULT_NETWORK_SCOPE", "192.168.1.0/24")
        return {
            "adapter_id": self.adapter_id,
            "adapter_class": self.__class__.__name__,
            "display_name": self.display_name,
            "is_simulated": True,
            "supports_real_enforcement": False,
            "status": "online_simulated",
            "status_label": "Activo (Entorno Simulado de Laboratorio)",
            "simulated_gateway": gateway_ip,
            "managed_scope": scope,
            "capabilities": [
                "Simulación de reserva DHCP por asociación IP/MAC",
                "Simulación de reglas de control de acceso por IP de origen (ACL L3)",
                "Simulación de ventanas horarias y perfiles de filtrado DNS",
                "Bitácora auditable de directivas generadas sin afectar la red anfitriona",
            ],
            "limitations_notice": (
                "Este adaptador opera exclusivamente en memoria/base de datos para fines de "
                "demostración académica. Las políticas marcadas como 'Aplicada en Simulador' "
                "no interceptan paquetes reales de la tarjeta de red del equipo."
            ),
        }

    def sync_device_state(self, device: Device) -> AdapterSyncResult:
        mac_info = device.mac_address or "SIN-MAC-CONOCIDA"
        action_map = {
            "authorized": "ACCEPT",
            "restricted": "MARK_RESTRICTED",
            "blocked": "DROP",
            "pending": "QUEUE_REVIEW",
        }
        rule_target = action_map.get(device.admin_status, "QUEUE_REVIEW")
        lease_cmd = (
            f"[SIMULADOR-LAB] dhcp-host={mac_info},{device.ip_address},{device.hostname or device.internal_code}"
            if device.mac_address and device.ip_assignment_type == "dhcp_reservation"
            else f"[SIMULADOR-LAB] ip-entry={device.ip_address} ({device.ip_assignment_type})"
        )
        acl_cmd = (
            f"[SIMULADOR-LAB] forward-acl src={device.ip_address} scope={device.network_scope} "
            f"mac={mac_info} -> action={rule_target}"
        )
        preview = f"{lease_cmd}\n{acl_cmd}"
        detail = (
            f"Simulación completada en laboratorio para {device.internal_code} ({device.ip_address}). "
            f"Directiva simulada: {rule_target}. Ningún router físico fue modificado."
        )
        return AdapterSyncResult(
            adapter_name=self.__class__.__name__,
            operation="SYNC_DEVICE_STATE",
            is_simulated=True,
            result_status="simulated_ok",
            device_sync_status="simulated_applied",
            policy_enforcement_status="simulated_in_lab",
            command_preview=preview,
            response_detail=detail,
        )

    def sync_policy_rule(self, policy: AccessPolicy) -> AdapterSyncResult:
        device = policy.device
        eff_status = policy.effective_status
        if eff_status != "active":
            preview = (
                f"[SIMULADOR-LAB] no-op policy_id={policy.id} state={eff_status} "
                f"src_ip={device.ip_address} (Política no vigente; se retira regla activa del simulador)"
            )
            detail = (
                f"La política '{policy.name}' tiene estado efectivo '{policy.effective_status_label}', "
                "por lo que el simulador registra su desactivación preventiva."
            )
        else:
            nav_extra = (
                f" profile=\"{policy.navigation_profile}\""
                if policy.navigation_profile
                else ""
            )
            until_str = (
                policy.valid_until.strftime("%Y-%m-%d %H:%M")
                if policy.valid_until
                else "PERMANENT"
            )
            preview = (
                f"[SIMULADOR-LAB] policy-rule id={policy.id} prio={policy.priority} "
                f"type={policy.policy_type} src={device.ip_address} "
                f"action={policy.action.upper()} valid_until={until_str}{nav_extra}"
            )
            detail = (
                f"Regla simulada para política '{policy.name}' sobre {device.ip_address} "
                f"con acción '{policy.action_label}'. (Modo Laboratorio: sin efecto en tráfico real)."
            )
        return AdapterSyncResult(
            adapter_name=self.__class__.__name__,
            operation="SYNC_ACCESS_POLICY",
            is_simulated=True,
            result_status="simulated_ok",
            device_sync_status="simulated_applied",
            policy_enforcement_status="simulated_in_lab",
            command_preview=preview,
            response_detail=detail,
        )


class PassiveNullRouterAdapter(RouterAdapterBase):
    """
    Adaptador Pasivo (Solo Base de Datos).
    Se utiliza cuando el administrador desea llevar únicamente el control documental
    y administrativo sin simular ni invocar un router externo.
    """

    adapter_id = "passive_only"
    display_name = "Modo Pasivo (Solo Registro en Base de Datos)"
    is_simulated = False
    supports_real_enforcement = False

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_class": self.__class__.__name__,
            "display_name": self.display_name,
            "is_simulated": False,
            "supports_real_enforcement": False,
            "status": "passive_only",
            "status_label": "Sin integración de Router (Registro Administrativo en BD)",
            "simulated_gateway": current_app.config.get("DEFAULT_GATEWAY_IP", "192.168.1.1"),
            "managed_scope": current_app.config.get("DEFAULT_NETWORK_SCOPE", "192.168.1.0/24"),
            "capabilities": [
                "Almacenamiento relacional de inventario IP/MAC, políticas y horarios",
                "Evaluación lógica de vigencias y detección de conflictos de IP",
                "Auditoría completa de cambios administrativos",
            ],
            "limitations_notice": (
                "No existe conexión activa con ningún router. Los registros permanecen en estado "
                "'Solo en BD' hasta que se configure un adaptador compatible o se apliquen manualmente."
            ),
        }

    def sync_device_state(self, device: Device) -> AdapterSyncResult:
        return AdapterSyncResult(
            adapter_name=self.__class__.__name__,
            operation="SYNC_DEVICE_STATE",
            is_simulated=False,
            result_status="not_applied_passive",
            device_sync_status="only_in_db",
            policy_enforcement_status="stored_in_db",
            command_preview="[MODO-PASIVO] Sin envío de comandos al router.",
            response_detail=(
                f"El dispositivo {device.internal_code} ({device.ip_address}) se encuentra guardado "
                "en la base de datos. El modo pasivo no realiza acciones sobre el router."
            ),
        )

    def sync_policy_rule(self, policy: AccessPolicy) -> AdapterSyncResult:
        return AdapterSyncResult(
            adapter_name=self.__class__.__name__,
            operation="SYNC_ACCESS_POLICY",
            is_simulated=False,
            result_status="not_applied_passive",
            device_sync_status="only_in_db",
            policy_enforcement_status="stored_in_db",
            command_preview="[MODO-PASIVO] Sin envío de reglas al router.",
            response_detail=(
                f"La política '{policy.name}' está registrada en la base de datos, pero no "
                "existe un adaptador de router activo para aplicarla al tráfico de red."
            ),
        )


def get_router_adapter(mode_override: Optional[str] = None) -> RouterAdapterBase:
    """Devuelve la instancia del adaptador configurado actualmente."""
    mode = mode_override or current_app.config.get("ROUTER_ADAPTER_MODE", "lab_simulator")
    if mode == "passive_only":
        return PassiveNullRouterAdapter()
    return LabSimulatorRouterAdapter()


def execute_device_router_sync(
    device: Device,
    triggered_by_id: Optional[int] = None,
    commit: bool = True,
) -> AdapterSyncResult:
    """
    Ejecuta la sincronización del dispositivo a través del adaptador activo,
    actualiza el estado de sincronización del dispositivo y guarda la traza en
    `router_sync_logs` y `audit_logs`.
    """
    adapter = get_router_adapter()
    result = adapter.sync_device_state(device)

    device.router_sync_status = result.device_sync_status
    device.last_synced_at = utc_now_naive()

    sync_log = RouterSyncLog(
        adapter_name=result.adapter_name,
        operation=result.operation,
        device_id=device.id,
        policy_id=None,
        is_simulated=result.is_simulated,
        result_status=result.result_status,
        command_preview=result.command_preview,
        response_detail=result.response_detail,
        triggered_by_id=triggered_by_id,
    )
    db.session.add(sync_log)

    log_audit_event(
        event_type="ROUTER_SYNC_DEVICE",
        module="router_adapter",
        description=result.response_detail,
        severity="info",
        user_id=triggered_by_id,
        target_type="device",
        target_id=device.id,
        metadata={
            "adapter": result.adapter_name,
            "is_simulated": result.is_simulated,
            "result_status": result.result_status,
            "device_sync_status": result.device_sync_status,
            "ip_address": device.ip_address,
        },
        commit=False,
    )

    if commit:
        db.session.commit()
    return result


def execute_policy_router_sync(
    policy: AccessPolicy,
    triggered_by_id: Optional[int] = None,
    commit: bool = True,
) -> AdapterSyncResult:
    """
    Ejecuta la sincronización de una política de acceso a través del adaptador activo,
    distinguiendo claramente entre almacenamiento en BD, simulación de laboratorio
    y confirmación real.
    """
    adapter = get_router_adapter()
    result = adapter.sync_policy_rule(policy)

    policy.enforcement_status = result.policy_enforcement_status
    policy.last_evaluated_at = utc_now_naive()

    sync_log = RouterSyncLog(
        adapter_name=result.adapter_name,
        operation=result.operation,
        device_id=policy.device_id,
        policy_id=policy.id,
        is_simulated=result.is_simulated,
        result_status=result.result_status,
        command_preview=result.command_preview,
        response_detail=result.response_detail,
        triggered_by_id=triggered_by_id,
    )
    db.session.add(sync_log)

    log_audit_event(
        event_type="ROUTER_SYNC_POLICY",
        module="router_adapter",
        description=result.response_detail,
        severity="info",
        user_id=triggered_by_id,
        target_type="policy",
        target_id=policy.id,
        metadata={
            "adapter": result.adapter_name,
            "is_simulated": result.is_simulated,
            "result_status": result.result_status,
            "enforcement_status": result.policy_enforcement_status,
            "policy_name": policy.name,
        },
        commit=False,
    )

    if commit:
        db.session.commit()
    return result

