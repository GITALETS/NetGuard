"""
Servicio de Detección y Verificación de Red en Tiempo Real (LAN / Wi-Fi / Mini-Módem).

Proporciona utilidades reales de sistema operativo (sin dependencias obligatorias externas)
para:
1. Detectar la dirección IP local del servidor, puerta de enlace (módem/mini-módem)
   y subred CIDR activa de la interfaz Wi-Fi actual.
2. Generar códigos QR en formato SVG local para abrir el sistema desde teléfonos móviles.
3. Descubrir dispositivos conectados en tiempo real mediante tabla ARP y barrido ICMP paralelo.
4. Ejecutar pruebas reales de conectividad (Ping ICMP con latencia en ms).
5. Evaluar en tiempo real el estado de acceso efectivo de un dispositivo según su IP,
   estado administrativo, horarios (individuales o globales) y políticas con intermitencia.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import io
import ipaddress
import os
import platform
import re
import socket
import subprocess
from typing import Any, Dict, List, Optional

from app.models.device import Device
from app.models.policy import AccessPolicy
from app.models.schedule import AccessSchedule
from app.models.user import utc_now_naive

# Bandera de Windows para evitar que las llamadas a ping/arp/ipconfig abran ventanas de consola
_SUBPROCESS_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0

_ARP_LINE_RE = re.compile(
    r"(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F]{2}(?:[:\-][0-9a-fA-F]{2}){5})"
)
_PING_TIME_RE = re.compile(r"(?:tiempo|time)\s*([=<])\s*([\d.]+)\s*ms?", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")


def _generate_qr_svg(url: str) -> Optional[str]:
    """
    Genera un código QR vectorial (SVG) localmente en memoria sin conexión a Internet.
    Si el paquete `qrcode` no está instalado en el entorno, devuelve None de forma segura.
    """
    if not url:
        return None
    try:
        import qrcode
        import qrcode.image.svg

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        buffer = io.BytesIO()
        img.save(buffer)
        svg_text = buffer.getvalue().decode("utf-8", errors="ignore")
        # Ajustar el SVG para que escale de manera responsiva dentro de su contenedor
        svg_text = re.sub(r'<\?xml[^>]*\?>\s*', "", svg_text)
        svg_text = svg_text.replace("<svg ", '<svg class="w-full h-full block" ', 1)
        return svg_text
    except Exception:
        return None


def _run_hidden_cmd(cmd: List[str], timeout_sec: float = 4.0) -> subprocess.CompletedProcess:
    """Ejecuta un comando del sistema de forma segura sin consola emergente y con tiempo límite."""
    cmd_encoding = "oem" if platform.system() == "Windows" else "utf-8"
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding=cmd_encoding,
        errors="replace",
        timeout=timeout_sec,
        shell=False,
        creationflags=_SUBPROCESS_FLAGS,
    )


def _detect_primary_local_ip() -> str:
    """
    Obtiene la dirección IPv4 activa de la tarjeta de red conectada al módem o Wi-Fi.
    Utiliza socket UDP sin transmitir tráfico real y respaldo mediante interfaces locales.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.5)
            sock.connect(("8.8.8.8", 80))
            candidate = sock.getsockname()[0]
            if candidate and not candidate.startswith("127."):
                return candidate
    except OSError:
        pass

    # Respaldo cuando el mini-módem aún no tiene salida externa a Internet
    try:
        import psutil

        for iface_name, addrs in psutil.net_if_addrs().items():
            lower_name = iface_name.lower()
            if any(skip in lower_name for skip in ("loopback", "vethernet", "vmware", "virtualbox")):
                continue
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address and not addr.address.startswith(("127.", "169.254.")):
                    return addr.address
    except ImportError:
        pass

    try:
        hostname = socket.gethostname()
        _, _, ip_list = socket.gethostbyname_ex(hostname)
        for ip in ip_list:
            if not ip.startswith(("127.", "169.254.")):
                return ip
    except OSError:
        pass

    return "127.0.0.1"


def _inspect_windows_ipconfig(target_ip: str) -> Dict[str, Optional[str]]:
    """Extrae máscara de subred, puerta de enlace e interfaz de Windows para la IP local activa."""
    result: Dict[str, Optional[str]] = {
        "interface_name": None,
        "netmask": None,
        "gateway_ip": None,
    }
    if platform.system() != "Windows" or target_ip == "127.0.0.1":
        return result

    try:
        proc = _run_hidden_cmd(["ipconfig"], timeout_sec=3.0)
        lines = proc.stdout.splitlines()
        current_adapter = None
        block_lines: List[str] = []
        blocks: List[tuple] = []

        for line in lines:
            if line and not line[0].isspace():
                if current_adapter:
                    blocks.append((current_adapter, block_lines))
                current_adapter = line.strip().rstrip(":")
                block_lines = []
            elif current_adapter:
                block_lines.append(line)
        if current_adapter:
            blocks.append((current_adapter, block_lines))

        for adapter_name, b_lines in blocks:
            joined = "\n".join(b_lines)
            if target_ip in joined:
                result["interface_name"] = adapter_name
                for bl in b_lines:
                    low = bl.lower()
                    ip_match = _IPV4_RE.search(bl)
                    if not ip_match:
                        continue
                    val_ip = ip_match.group(1)
                    if any(k in low for k in ("máscara", "mascara", "subnet mask")):
                        result["netmask"] = val_ip
                    elif any(k in low for k in ("puerta de enlace", "default gateway")):
                        if val_ip != target_ip:
                            result["gateway_ip"] = val_ip
                break
    except Exception:
        pass
    return result


def detect_local_network_info(port: Optional[int] = None) -> Dict[str, Any]:
    """
    Detecta de forma automática los parámetros de red de la interfaz Wi-Fi/LAN activa
    (útil al cambiar de módem doméstico a un mini-módem portátil con chip o hotspot).
    """
    resolved_port = port or int(os.environ.get("FLASK_RUN_PORT", "5000"))
    local_ip = _detect_primary_local_ip()
    netmask = "255.255.255.0"
    interface_name = "Wi-Fi / Red Local"
    gateway_ip = None

    # 1. Intentar lectura precisa con psutil si está disponible
    try:
        import psutil

        for iface_name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == socket.AF_INET and addr.address == local_ip:
                    interface_name = iface_name
                    if addr.netmask:
                        netmask = addr.netmask
                    break
    except ImportError:
        pass

    # 2. Complementar puerta de enlace y máscara mediante ipconfig en Windows
    win_info = _inspect_windows_ipconfig(local_ip)
    if win_info.get("interface_name"):
        interface_name = win_info["interface_name"]
    if win_info.get("netmask"):
        netmask = win_info["netmask"]
    if win_info.get("gateway_ip"):
        gateway_ip = win_info["gateway_ip"]

    # Calcular subred CIDR real y segmento rápido /24 para barrido ágil
    if local_ip == "127.0.0.1":
        network_scope = "192.168.1.0/24"
        scan_cidr = "192.168.1.0/24"
        gateway_ip = gateway_ip or "192.168.1.1"
        ip_prefix = "192.168.1."
    else:
        try:
            net_obj = ipaddress.IPv4Network(f"{local_ip}/{netmask}", strict=False)
            network_scope = str(net_obj)
            # Para redes muy grandes (/16 o /20), acotar el ping sweep a la subred /24 local
            if net_obj.prefixlen < 24:
                scan_cidr = str(ipaddress.IPv4Network(f"{local_ip}/24", strict=False))
            else:
                scan_cidr = network_scope
        except ValueError:
            network_scope = str(ipaddress.IPv4Network(f"{local_ip}/24", strict=False))
            scan_cidr = network_scope

        octets = local_ip.split(".")
        ip_prefix = f"{octets[0]}.{octets[1]}.{octets[2]}."
        if not gateway_ip:
            gateway_ip = f"{ip_prefix}1"

    mobile_url = f"http://{local_ip}:{resolved_port}"
    client_status_url = f"http://{local_ip}:{resolved_port}/network/mi-acceso"

    return {
        "local_ip": local_ip,
        "netmask": netmask,
        "network_scope": network_scope,
        "scan_cidr": scan_cidr,
        "gateway_ip": gateway_ip,
        "ip_prefix": ip_prefix,
        "interface_name": interface_name,
        "server_hostname": socket.gethostname(),
        "port": resolved_port,
        "is_lan_reachable": local_ip != "127.0.0.1",
        "mobile_url": mobile_url,
        "client_status_url": client_status_url,
        "qr_svg_main": _generate_qr_svg(mobile_url) if local_ip != "127.0.0.1" else None,
        "qr_svg_client": _generate_qr_svg(client_status_url) if local_ip != "127.0.0.1" else None,
        "detected_at": datetime.now().strftime("%H:%M:%S"),
    }


def ping_host(ip_address: str, timeout_ms: int = 800) -> Dict[str, Any]:
    """
    Ejecuta una sonda ICMP (Ping) real hacia la dirección IP solicitada.
    Valida estrictamente que sea una IP válida para prevenir inyección de comandos.
    """
    try:
        ip_obj = ipaddress.ip_address((ip_address or "").strip())
    except ValueError:
        return {
            "ip_address": str(ip_address),
            "online": False,
            "latency_ms": None,
            "detail": "Dirección IP no válida.",
            "checked_at": datetime.now().strftime("%H:%M:%S"),
        }

    ip_clean = str(ip_obj)
    is_windows = platform.system() == "Windows"
    if is_windows:
        cmd = ["ping", "-n", "1", "-w", str(max(100, timeout_ms)), ip_clean]
    else:
        wait_sec = max(1, int(round(timeout_ms / 1000.0)))
        cmd = ["ping", "-c", "1", "-W", str(wait_sec), ip_clean]

    try:
        proc = _run_hidden_cmd(cmd, timeout_sec=max(2.0, (timeout_ms / 1000.0) + 1.5))
        stdout = proc.stdout or ""
        upper = stdout.upper()
        time_match = _PING_TIME_RE.search(stdout)
        has_ttl = "TTL=" in upper

        if proc.returncode == 0 and (has_ttl or time_match):
            latency = None
            if time_match:
                op, val_str = time_match.group(1), time_match.group(2)
                try:
                    latency = 0.5 if op == "<" and float(val_str) <= 1.0 else round(float(val_str), 1)
                except ValueError:
                    latency = None
            return {
                "ip_address": ip_clean,
                "online": True,
                "latency_ms": latency,
                "detail": f"En línea (respuesta ICMP en {latency} ms)" if latency is not None else "En línea (respuesta ICMP)",
                "checked_at": datetime.now().strftime("%H:%M:%S"),
            }

        return {
            "ip_address": ip_clean,
            "online": False,
            "latency_ms": None,
            "detail": "Sin respuesta ICMP (equipo desconectado o firewall bloqueando ping)",
            "checked_at": datetime.now().strftime("%H:%M:%S"),
        }
    except subprocess.TimeoutExpired:
        return {
            "ip_address": ip_clean,
            "online": False,
            "latency_ms": None,
            "detail": "Tiempo de espera agotado",
            "checked_at": datetime.now().strftime("%H:%M:%S"),
        }
    except Exception as exc:
        return {
            "ip_address": ip_clean,
            "online": False,
            "latency_ms": None,
            "detail": f"No se pudo sondear: {exc}",
            "checked_at": datetime.now().strftime("%H:%M:%S"),
        }


def read_arp_table() -> Dict[str, str]:
    """Lee la caché ARP actual del sistema operativo y devuelve un mapa `{ip: MAC_CANÓNICA}`."""
    arp_map: Dict[str, str] = {}
    try:
        proc = _run_hidden_cmd(["arp", "-a"], timeout_sec=3.0)
        for line in (proc.stdout or "").splitlines():
            match = _ARP_LINE_RE.search(line)
            if not match:
                continue
            ip_str, mac_raw = match.group(1), match.group(2)
            try:
                ip_obj = ipaddress.IPv4Address(ip_str)
                if ip_obj.is_multicast or ip_obj.is_loopback or ip_obj.is_unspecified:
                    continue
            except ValueError:
                continue

            mac_hex = re.sub(r"[:\-]", "", mac_raw).upper()
            if len(mac_hex) != 12 or mac_hex in ("000000000000", "FFFFFFFFFFFF"):
                continue
            mac_norm = ":".join(mac_hex[i : i + 2] for i in range(0, 12, 2))
            if ip_str.endswith(".255"):
                continue
            arp_map[ip_str] = mac_norm
    except Exception:
        pass
    return arp_map


def _safe_reverse_dns(ip_str: str) -> Optional[str]:
    """Intenta obtener el nombre de host en red local con tiempo límite corto."""
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(0.2)
        name, _, _ = socket.gethostbyaddr(ip_str)
        if name and name != ip_str:
            return name
    except Exception:
        return None
    finally:
        socket.setdefaulttimeout(old_timeout)
    return None


def scan_active_network(include_ping_sweep: bool = True) -> Dict[str, Any]:
    """
    Escanea la red Wi-Fi / Mini-Módem activa en tiempo real combinando:
    - Tabla ARP del sistema operativo (direcciones IP y MAC físicas reales).
    - Barrido ICMP concurrente sobre el segmento /24 activo para descubrir teléfonos activos.
    - Cruce automático contra los dispositivos registrados en la base de datos MySQL.
    """
    net_info = detect_local_network_info()
    local_ip = net_info["local_ip"]
    gateway_ip = net_info["gateway_ip"]
    network_scope = net_info["network_scope"]
    scan_cidr = net_info["scan_cidr"]

    live_pings: Dict[str, Dict[str, Any]] = {}

    if include_ping_sweep and local_ip != "127.0.0.1":
        try:
            net_obj = ipaddress.IPv4Network(scan_cidr, strict=False)
            candidates = [str(host) for host in net_obj.hosts()]
            if gateway_ip and gateway_ip not in candidates:
                candidates.insert(0, gateway_ip)

            # Incluir también IPs registradas no-demo para comprobar si responden aunque estén en otro octeto
            existing_devices = Device.query.filter_by(is_demo=False).all()
            for dev in existing_devices:
                if dev.ip_address not in candidates:
                    candidates.append(dev.ip_address)

            # Límite seguro de hosts por barrido
            candidates = candidates[:260]
            with ThreadPoolExecutor(max_workers=48) as pool:
                future_map = {pool.submit(ping_host, ip, 320): ip for ip in candidates}
                for fut in as_completed(future_map):
                    res = fut.result()
                    if res["online"]:
                        live_pings[res["ip_address"]] = res
        except Exception:
            pass

    # Leer tabla ARP actualizada después del barrido ICMP
    arp_map = read_arp_table()

    try:
        active_net = ipaddress.IPv4Network(network_scope, strict=False)
    except ValueError:
        active_net = None

    # Solo sondear vecinos ARP en el modo escaneo activo (la carga inicial es instantánea < 50ms)
    if include_ping_sweep:
        arp_candidates = []
        for arp_ip in arp_map:
            if arp_ip == local_ip or arp_ip in live_pings:
                continue
            if active_net:
                try:
                    if ipaddress.IPv4Address(arp_ip) not in active_net:
                        continue
                except ValueError:
                    continue
            arp_candidates.append(arp_ip)

        if arp_candidates:
            with ThreadPoolExecutor(max_workers=24) as pool:
                for fut in as_completed([pool.submit(ping_host, ip, 450) for ip in arp_candidates]):
                    res = fut.result()
                    live_pings[res["ip_address"]] = res

    # Construir conjunto unificado de IPs activas en el mini-módem/Wi-Fi
    all_ips = set(live_pings.keys())
    if local_ip != "127.0.0.1":
        all_ips.add(local_ip)
    for arp_ip in arp_map:
        if active_net:
            try:
                if ipaddress.IPv4Address(arp_ip) in active_net:
                    all_ips.add(arp_ip)
            except ValueError:
                pass

    # Cargar catálogo registrado en BD para cruzar coincidencias
    db_devices = Device.query.all()
    by_ip = {}
    by_mac = {}
    for dev in db_devices:
        if dev.ip_address not in by_ip or not dev.is_demo:
            by_ip[dev.ip_address] = dev
        if dev.mac_address:
            by_mac[dev.mac_address.upper()] = dev

    # Resolución paralela opcional de hostnames en redes locales (sin bloquear en shutdown)
    hostnames_map: Dict[str, Optional[str]] = {}
    if include_ping_sweep:
        online_targets = [ip for ip in all_ips if ip != local_ip and ip != gateway_ip and live_pings.get(ip, {}).get("online")]
        if online_targets:
            from concurrent.futures import wait as futures_wait

            dns_pool = ThreadPoolExecutor(max_workers=12)
            try:
                fut_map = {dns_pool.submit(_safe_reverse_dns, ip): ip for ip in online_targets[:24]}
                done, _ = futures_wait(fut_map.keys(), timeout=0.8)
                for fut in done:
                    target_ip = fut_map[fut]
                    try:
                        hostnames_map[target_ip] = fut.result()
                    except Exception:
                        hostnames_map[target_ip] = None
            finally:
                dns_pool.shutdown(wait=False, cancel_futures=True)

    discovered: List[Dict[str, Any]] = []
    for ip_str in sorted(all_ips, key=lambda x: tuple(int(p) for p in x.split("."))):
        mac = arp_map.get(ip_str)
        ping_res = live_pings.get(ip_str)
        is_this_server = ip_str == local_ip
        is_gateway = ip_str == gateway_ip
        is_online = True if is_this_server else bool(ping_res and ping_res.get("online"))
        latency_ms = 0.0 if is_this_server else (ping_res.get("latency_ms") if ping_res else None)

        reg_dev = by_ip.get(ip_str) or (by_mac.get(mac.upper()) if mac else None)

        # Sugerir rol amigable y nombre automático para registro de 1 clic
        hostname = None
        if is_this_server:
            hostname = net_info["server_hostname"]
            suggested_name = f"Laptop Servidor ({hostname})"
            suggested_type = "laptop"
        elif is_gateway:
            suggested_name = "Mini-Modem / Router Wi-Fi"
            suggested_type = "other"
        else:
            hostname = hostnames_map.get(ip_str)
            suggested_name = hostname or f"Equipo Wi-Fi ({ip_str.split('.')[-1]})"
            suggested_type = "smartphone"

        discovered.append(
            {
                "ip_address": ip_str,
                "mac_address": mac,
                "hostname": hostname,
                "suggested_name": suggested_name,
                "suggested_type": suggested_type,
                "is_online": is_online,
                "latency_ms": latency_ms,
                "is_this_server": is_this_server,
                "is_gateway": is_gateway,
                "in_arp_cache": ip_str in arp_map,
                "registered_device": (
                    {
                        "id": reg_dev.id,
                        "name": reg_dev.name,
                        "internal_code": reg_dev.internal_code,
                        "admin_status": reg_dev.admin_status,
                        "admin_status_label": reg_dev.admin_status_label,
                        "is_demo": reg_dev.is_demo,
                    }
                    if reg_dev
                    else None
                ),
            }
        )

    # Ordenar: dispositivos en línea primero, poniendo arriba los teléfonos/equipos cliente antes del gateway
    discovered.sort(
        key=lambda d: (
            not d["is_online"],
            d["is_gateway"],
            d["is_this_server"],
            tuple(int(p) for p in d["ip_address"].split(".")),
        )
    )

    return {
        "network_info": net_info,
        "discovered": discovered,
        "online_count": sum(1 for d in discovered if d["is_online"]),
        "registered_count": sum(1 for d in discovered if d["registered_device"] is not None),
        "scanned_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def evaluate_live_device_access(
    ip_address: str,
    local_ref_dt: Optional[datetime] = None,
    utc_ref_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Evalúa en tiempo real el estado efectivo de acceso a Internet de un dispositivo
    conectado al módem/mini-módem a partir de su dirección IP real.

    Cruza en orden jerárquico:
    1. Registro del dispositivo y su estado administrativo (`blocked`, `pending`, `restricted`, `authorized`).
    2. Ventanas de Horarios Familiares activas (`restricted_window` y `allowed_window`),
       incluyendo horarios globales asignados a toda la casa (`device_id IS NULL`).
    3. Políticas de acceso vigentes ordenadas por prioridad, incluyendo el cálculo en vivo
       de fases del Intermediario de Intermitencia (ventana activa vs ventana de pausa).
    """
    clean_ip = (ip_address or "").strip()
    local_now = local_ref_dt or datetime.now()
    utc_now = utc_ref_dt or utc_now_naive()

    # Buscar dispositivo por IP (priorizando registros reales sobre demo)
    matches = Device.query.filter_by(ip_address=clean_ip).order_by(Device.is_demo.asc(), Device.id.asc()).all()
    device = matches[0] if matches else None

    if not device:
        return {
            "found": False,
            "ip_address": clean_ip,
            "verdict_code": "unregistered",
            "verdict_label": "Equipo No Registrado en NetGuard",
            "verdict_color": "slate",
            "reason": (
                f"La dirección IP {clean_ip} está conectada a la red pero aún no ha sido dada de alta "
                "en el inventario familiar."
            ),
            "evaluated_at": local_now.strftime("%d/%m/%Y %H:%M:%S"),
            "device": None,
            "active_schedules": [],
            "active_policies": [],
            "intermittent_status": None,
        }

    # Evaluar horarios aplicables al dispositivo (específicos + globales si no está bloqueado)
    all_active_schedules = (
        AccessSchedule.query.filter(
            AccessSchedule.is_active.is_(True),
            db_or_schedule_filter(device.id),
        )
        .order_by(AccessSchedule.created_at.desc())
        .all()
    )

    schedule_summaries = []
    allowed_windows_defined = []
    in_any_allowed_window = False
    triggered_restricted_schedule = None

    for sch in all_active_schedules:
        in_window = sch.is_in_window_at(local_now)
        schedule_summaries.append(
            {
                "id": sch.id,
                "label": sch.label,
                "is_global": sch.is_global,
                "behavior": sch.window_behavior,
                "behavior_label": sch.behavior_label,
                "hours": f"{sch.start_time} a {sch.end_time}",
                "in_window_now": in_window,
            }
        )
        if sch.window_behavior == "restricted_window" and in_window and not triggered_restricted_schedule:
            triggered_restricted_schedule = sch
        elif sch.window_behavior == "allowed_window":
            allowed_windows_defined.append(sch)
            if in_window:
                in_any_allowed_window = True

    # Evaluar políticas activas vigentes ordenadas por prioridad
    device_policies = (
        AccessPolicy.query.filter_by(device_id=device.id, status="active")
        .order_by(AccessPolicy.priority.asc(), AccessPolicy.created_at.desc())
        .all()
    )
    active_policies_info = []
    blocking_policy = None
    restricting_policy = None
    intermittent_status = None

    for pol in device_policies:
        if pol.effective_status_at(utc_now) != "active":
            continue

        cycle_info = None
        if pol.is_intermittent or pol.policy_type == "intermittent_intermediary":
            active_m = max(1, int(pol.interval_active_minutes or 30))
            pause_m = max(1, int(pol.interval_pause_minutes or 15))
            cycle_total_sec = (active_m + pause_m) * 60
            ref_start = pol.valid_from or utc_now
            elapsed_sec = max(0, int((utc_now - ref_start).total_seconds()))
            pos_sec = elapsed_sec % cycle_total_sec
            active_sec = active_m * 60

            if pos_sec < active_sec:
                phase = "active_window"
                phase_label = "Ventana Activa (Uso permitido temporalmente)"
                remaining_sec = active_sec - pos_sec
                progress_pct = round((pos_sec / active_sec) * 100)
            else:
                phase = "pause_window"
                phase_label = "Ventana de Pausa (Descanso / Corte Intermitente)"
                remaining_sec = cycle_total_sec - pos_sec
                progress_pct = round(((pos_sec - active_sec) / (pause_m * 60)) * 100)

            cycle_info = {
                "policy_id": pol.id,
                "policy_name": pol.name,
                "target": pol.target_domain or pol.navigation_profile or "Internet General",
                "active_minutes": active_m,
                "pause_minutes": pause_m,
                "phase": phase,
                "phase_label": phase_label,
                "remaining_seconds": remaining_sec,
                "remaining_mmss": f"{remaining_sec // 60:02d}:{remaining_sec % 60:02d}",
                "progress_percent": progress_pct,
            }
            if intermittent_status is None:
                intermittent_status = cycle_info

        active_policies_info.append(
            {
                "id": pol.id,
                "name": pol.name,
                "policy_type_label": pol.policy_type_label,
                "action": pol.action,
                "action_label": pol.action_label,
                "target_domain": pol.target_domain,
                "navigation_profile": pol.navigation_profile,
                "is_intermittent": pol.is_intermittent,
                "cycle_info": cycle_info,
            }
        )

        if pol.action == "block" and blocking_policy is None:
            blocking_policy = pol
        elif pol.action == "restrict" and restricting_policy is None:
            restricting_policy = pol

    # Determinar veredicto final jerárquico en tiempo real
    if device.admin_status == "blocked":
        verdict_code = "blocked"
        verdict_label = "Internet Apagado / Bloqueado"
        verdict_color = "rose"
        reason = (
            f"El administrador ha bloqueado el acceso de '{device.name}'. "
            "Los horarios generales quedan excluidos para este equipo."
        )
    elif device.admin_status == "pending":
        verdict_code = "pending"
        verdict_label = "Pendiente de Autorización"
        verdict_color = "slate"
        reason = "Este equipo está registrado pero aún espera aprobación para navegar."
    elif triggered_restricted_schedule is not None:
        verdict_code = "schedule_paused"
        verdict_label = "Pausado por Horario Familiar"
        verdict_color = "amber"
        scope_tag = "horario global de toda la casa" if triggered_restricted_schedule.is_global else "horario asignado"
        reason = (
            f"Actualmente aplica el {scope_tag} '{triggered_restricted_schedule.label}' "
            f"({triggered_restricted_schedule.start_time} a {triggered_restricted_schedule.end_time})."
        )
    elif allowed_windows_defined and not in_any_allowed_window:
        verdict_code = "schedule_paused"
        verdict_label = "Fuera de Horario Permitido"
        verdict_color = "amber"
        reason = "Este equipo tiene horarios permitidos configurados y la hora actual está fuera de ventana."
    elif blocking_policy is not None:
        verdict_code = "blocked"
        verdict_label = "Bloqueado por Política de Red"
        verdict_color = "rose"
        reason = f"Política vigente '{blocking_policy.name}' bloquea el tráfico hacia {blocking_policy.target_domain or 'Internet'}."
    elif intermittent_status and intermittent_status["phase"] == "pause_window":
        verdict_code = "intermittent_pause"
        verdict_label = "Pausa de Intermitencia Activa"
        verdict_color = "amber"
        reason = (
            f"El intermediario '{intermittent_status['policy_name']}' se encuentra en fase de descanso "
            f"para {intermittent_status['target']} (reanuda en {intermittent_status['remaining_mmss']})."
        )
    elif device.admin_status == "restricted" or restricting_policy is not None or intermittent_status is not None:
        verdict_code = "restricted"
        verdict_label = "Acceso Supervisado / Limitado"
        verdict_color = "cyan"
        if intermittent_status:
            reason = (
                f"En ventana activa de intermitencia para '{intermittent_status['target']}' "
                f"(siguiente pausa en {intermittent_status['remaining_mmss']})."
            )
        elif restricting_policy:
            reason = f"Política supervisada '{restricting_policy.name}': {restricting_policy.navigation_profile or restricting_policy.target_domain or 'Filtro familiar activo'}."
        else:
            reason = "Este dispositivo opera en modo supervisado (Pausa / Modo Estudio)."
    else:
        verdict_code = "allowed"
        verdict_label = "Internet Libre (Acceso Autorizado)"
        verdict_color = "emerald"
        reason = "Conexión autorizada con normalidad y sin restricciones activas en este instante."

    return {
        "found": True,
        "ip_address": clean_ip,
        "verdict_code": verdict_code,
        "verdict_label": verdict_label,
        "verdict_color": verdict_color,
        "reason": reason,
        "evaluated_at": local_now.strftime("%d/%m/%Y %H:%M:%S"),
        "device": {
            "id": device.id,
            "name": device.name,
            "internal_code": device.internal_code,
            "profile_label": device.profile_label,
            "owner_label": device.owner_label or "Uso familiar",
            "mac_address": device.mac_address or "No registrada",
            "network_scope": device.network_scope,
            "admin_status": device.admin_status,
            "admin_status_label": device.admin_status_label,
            "router_sync_label": device.router_sync_label,
        },
        "active_schedules": schedule_summaries,
        "active_policies": active_policies_info,
        "intermittent_status": intermittent_status,
    }


def db_or_schedule_filter(device_id: int):
    """Devuelve condición SQLAlchemy para horarios del dispositivo o horarios globales."""
    from sqlalchemy import or_

    return or_(AccessSchedule.device_id == device_id, AccessSchedule.device_id.is_(None))
