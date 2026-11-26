"""
Servidor Proxy Intermediario HTTP/HTTPS Real (Capa de Aplicacion - Puerto TCP 8888).

Actua como intermediario fisico de red en la laptop cuando los dispositivos
moviles (conectados al mini-modem o hotspot) configuran su Proxy Wi-Fi hacia la
IP de este servidor. Evalua en tiempo real contra MySQL las reglas configuradas
en NetGuard Home IP para cada direccion IP:

1. Bloqueo / Pausa Total: corta conexiones nuevas y cierra tuneles HTTPS activos
   en menos de 1.5 segundos.
2. Modo Estudio: bloquea dominios recreativos, video y redes sociales (YouTube,
   TikTok, Roblox, Instagram, etc.) permitiendo portales educativos y busqueda.
3. Intermediario con Intermitencia: permite o bloquea dominios especificos segun
   la fase vigente del ciclo (ventana activa vs ventana de pausa).
4. Acceso al Portal NetGuard: siempre se permite para evitar autobloqueos desde
   los telefonos durante la demostracion.
"""

from collections import deque
from datetime import datetime
import os
import select
import socket
import socketserver
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from app.extensions import db
from app.services.network_probe_service import evaluate_live_device_access

# Contador global de version de politicas: al incrementarse, fuerza la re-evaluacion
# inmediata de todos los tuneles activos y limpia la cache en memoria.
_policy_version_lock = threading.Lock()
_policy_version: int = 1

# Cache breve (1s) keyed por (client_ip, host, policy_version)
_decision_cache: Dict[Tuple[str, str, int], Tuple[float, Dict[str, Any]]] = {}

# Bitacora circular en memoria de las ultimas conexiones evaluadas por el intermediario
_proxy_events_lock = threading.Lock()
_proxy_events: deque = deque(maxlen=50)

# Estado del demonio de proxy en ejecucion
_proxy_server_instance: Optional[socketserver.ThreadingTCPServer] = None
_proxy_server_port: int = int(os.environ.get("NETGUARD_PROXY_PORT", "8888"))
_proxy_running: bool = False
_local_ips_cache: Tuple[float, Tuple[str, ...]] = (0.0, ())


def _get_dynamic_server_ips(configured_ips: Tuple[str, ...] = ()) -> Tuple[str, ...]:
    """Devuelve las IPs locales activas (con cache de 5s) para permitir el portal tras cambios de Wi-Fi."""
    global _local_ips_cache
    now_ts = time.monotonic()
    cached_ts, cached_ips = _local_ips_cache
    if (now_ts - cached_ts) < 5.0 and cached_ips:
        return tuple(set(configured_ips) | set(cached_ips))

    found = set(configured_ips) | {"127.0.0.1", "localhost", "::1"}
    try:
        for res in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            ip_val = res[4][0]
            if ip_val:
                found.add(ip_val)
    except Exception:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        found.add(sock.getsockname()[0])
        sock.close()
    except Exception:
        pass

    frozen = tuple(found)
    _local_ips_cache = (now_ts, frozen)
    return frozen

# Familias de dominios asociados cuando una regla apunta a un servicio especifico
DOMAIN_COMPANIONS: Dict[str, Tuple[str, ...]] = {
    "youtube.com": ("youtube.com", "youtu.be", "googlevideo.com", "ytimg.com", "yt3.ggpht.com", "youtube-nocookie.com", "youtubei.googleapis.com"),
    "tiktok.com": (
        "tiktok.com",
        "tiktokcdn.com",
        "tiktokcdn-us.com",
        "tiktokv.com",
        "tiktokv.us",
        "tiktokw.us",
        "musical.ly",
        "muscdn.com",
        "byteoversea.com",
        "bytedance.com",
        "byteimg.com",
        "ibytedtos.com",
        "ttlivecdn.com",
    ),
    "roblox.com": ("roblox.com", "rbxcdn.com", "robloxlabs.com"),
    "facebook.com": ("facebook.com", "fbcdn.net", "fbsbx.com", "messenger.com"),
    "instagram.com": ("instagram.com", "cdninstagram.com"),
    "twitch.tv": ("twitch.tv", "ttvnw.net", "jtvnw.net"),
    "netflix.com": ("netflix.com", "nflxvideo.net", "nflximg.net"),
    "spotify.com": ("spotify.com", "scdn.co"),
    "x.com": ("x.com", "twitter.com", "twimg.com"),
    "twitter.com": ("twitter.com", "x.com", "twimg.com"),
}

# Lista curada de servicios recreativos restringidos en Modo Estudio
STUDY_BLOCKED_DOMAINS: Tuple[str, ...] = (
    "youtube.com",
    "youtu.be",
    "googlevideo.com",
    "ytimg.com",
    "youtubei.googleapis.com",
    "tiktok.com",
    "tiktokcdn.com",
    "tiktokcdn-us.com",
    "tiktokv.com",
    "tiktokv.us",
    "tiktokw.us",
    "muscdn.com",
    "byteoversea.com",
    "bytedance.com",
    "byteimg.com",
    "ibytedtos.com",
    "ttlivecdn.com",
    "instagram.com",
    "cdninstagram.com",
    "facebook.com",
    "fbcdn.net",
    "messenger.com",
    "roblox.com",
    "rbxcdn.com",
    "twitch.tv",
    "ttvnw.net",
    "netflix.com",
    "nflxvideo.net",
    "disneyplus.com",
    "primevideo.com",
    "spotify.com",
    "discord.com",
    "discordapp.com",
    "reddit.com",
    "x.com",
    "twitter.com",
    "twimg.com",
    "steampowered.com",
    "epicgames.com",
    "kick.com",
    "9gag.com",
)


def bump_proxy_policy_version() -> int:
    """Invalida la cache de decisiones y notifica a los tuneles activos para re-evaluar."""
    global _policy_version
    with _policy_version_lock:
        _policy_version += 1
        _decision_cache.clear()
        return _policy_version


def get_proxy_policy_version() -> int:
    """Obtiene el numero actual de version de reglas para deteccion de cambios."""
    with _policy_version_lock:
        return _policy_version


def get_proxy_status() -> Dict[str, Any]:
    """Devuelve el estado tecnico actual y los ultimos eventos interceptados por el proxy."""
    with _proxy_events_lock:
        recent = list(_proxy_events)
    return {
        "running": _proxy_running,
        "port": _proxy_server_port,
        "policy_version": get_proxy_policy_version(),
        "recent_events": recent,
    }


def _record_proxy_event(client_ip: str, host: str, allowed: bool, action_code: str, reason: str, device_name: Optional[str] = None) -> None:
    """Registra una decision relevante del intermediario en la bitacora circular en memoria."""
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "client_ip": client_ip,
        "device_name": device_name or client_ip,
        "host": host,
        "allowed": allowed,
        "action_code": action_code,
        "reason": reason,
    }
    with _proxy_events_lock:
        # Evitar inundar el historial con peticiones repetidas consecutivas identicas en el mismo segundo
        if _proxy_events:
            top = _proxy_events[0]
            if top["client_ip"] == client_ip and top["host"] == host and top["action_code"] == action_code and top["time"] == entry["time"]:
                return
        _proxy_events.appendleft(entry)


def _domain_matches(host: str, pattern: str) -> bool:
    """Comprueba si un hostname coincide exactamente o es subdominio del patron objetivo."""
    h = (host or "").strip().lower().rstrip(".")
    p = (pattern or "").strip().lower().lstrip("*.")
    if not h or not p:
        return False
    # Expandir si existe grupo de dominios acompanantes (ej. youtube.com -> googlevideo.com)
    candidates = DOMAIN_COMPANIONS.get(p, (p,))
    for cand in candidates:
        if h == cand or h.endswith(f".{cand}"):
            return True
    return False


def _matches_target_list(host: str, raw_target: Optional[str]) -> bool:
    """Evalua una cadena con uno o varios dominios separados por coma."""
    if not raw_target:
        return True
    tokens = [t.strip() for t in re_split_domains(raw_target) if t.strip()]
    return any(_domain_matches(host, tok) for tok in tokens)


def re_split_domains(text: str) -> List[str]:
    """Divide dominios separados por comas, espacios o punto y coma."""
    import re
    return re.split(r"[,;\s]+", text)


def evaluate_proxy_request(
    client_ip: str,
    target_host: str,
    target_port: int = 443,
    flask_port: int = 5000,
    server_ips: Optional[Tuple[str, ...]] = None,
) -> Dict[str, Any]:
    """
    Determina en tiempo real si el intermediario debe permitir (`allowed=True`)
    o bloquear (`allowed=False`) una peticion HTTP/HTTPS procedente de `client_ip`
    hacia `target_host`.
    """
    clean_host = (target_host or "").strip().lower()
    known_local = set(server_ips or ()) | {"127.0.0.1", "localhost", "::1"}

    # Permitir siempre el acceso al propio panel web/portal NetGuard para no perder control
    if clean_host in known_local and target_port in (flask_port, 80, 443):
        return {
            "allowed": True,
            "action_code": "NETGUARD_SELF",
            "reason": "Acceso al portal local NetGuard permitido.",
            "device_name": None,
        }

    # Revisar cache de 1 segundo con la version vigente de politicas
    cur_ver = get_proxy_policy_version()
    cache_key = (client_ip, clean_host, cur_ver)
    now_ts = time.monotonic()
    cached = _decision_cache.get(cache_key)
    if cached and (now_ts - cached[0]) < 1.0:
        return cached[1]

    ev = evaluate_live_device_access(client_ip)
    dev = ev.get("device")
    dev_name = dev["name"] if dev else None

    if not ev.get("found"):
        res = {
            "allowed": True,
            "action_code": "UNREGISTERED_PASS",
            "reason": "Equipo aun sin registrar en NetGuard (trafico permitido por defecto).",
            "device_name": None,
        }
        _decision_cache[cache_key] = (now_ts, res)
        return res

    verdict = ev.get("verdict_code")

    # 1. Bloqueo administrativo total, pausa familiar o pausa por horario
    if verdict in ("blocked", "schedule_paused", "pending"):
        res = {
            "allowed": False,
            "action_code": f"DENY_{verdict.upper()}",
            "reason": ev.get("reason") or "Acceso bloqueado o pausado por NetGuard.",
            "device_name": dev_name,
        }
        _decision_cache[cache_key] = (now_ts, res)
        return res

    # 2. Evaluacion de politicas especificas por dominio y ciclos de intermitencia
    for pol in ev.get("active_policies", []):
        target_domain = pol.get("target_domain")
        nav_profile = (pol.get("navigation_profile") or "").lower()
        cycle = pol.get("cycle_info")

        # Politica de intermitencia activa
        if cycle is not None:
            applies_to_host = True if not target_domain else _matches_target_list(clean_host, target_domain)
            if applies_to_host:
                if cycle["phase"] == "pause_window":
                    res = {
                        "allowed": False,
                        "action_code": "DENY_INTERMITTENT_PAUSE",
                        "reason": (
                            f"Pausa de intermitencia en '{pol['name']}' hacia {clean_host} "
                            f"(reanuda en {cycle['remaining_mmss']})."
                        ),
                        "device_name": dev_name,
                    }
                    _decision_cache[cache_key] = (now_ts, res)
                    return res
                # En ventana activa de intermitencia para este dominio
                continue

        # Politica de bloqueo total o sobre dominio especifico
        if pol["action"] == "block":
            if not target_domain or _matches_target_list(clean_host, target_domain):
                res = {
                    "allowed": False,
                    "action_code": "DENY_POLICY_BLOCK",
                    "reason": f"Bloqueado por regla '{pol['name']}'.",
                    "device_name": dev_name,
                }
                _decision_cache[cache_key] = (now_ts, res)
                return res

        # Politica de restriccion / Modo Estudio
        if pol["action"] == "restrict":
            if target_domain and _matches_target_list(clean_host, target_domain):
                res = {
                    "allowed": False,
                    "action_code": "DENY_DOMAIN_FILTER",
                    "reason": f"Dominio filtrado por regla '{pol['name']}'.",
                    "device_name": dev_name,
                }
                _decision_cache[cache_key] = (now_ts, res)
                return res

            if "estudio" in nav_profile or "recreativ" in nav_profile or "adult" in nav_profile:
                if any(_domain_matches(clean_host, d) for d in STUDY_BLOCKED_DOMAINS):
                    res = {
                        "allowed": False,
                        "action_code": "DENY_STUDY_MODE",
                        "reason": f"Sitio recreativo bloqueado por Modo Estudio ({clean_host}).",
                        "device_name": dev_name,
                    }
                    _decision_cache[cache_key] = (now_ts, res)
                    return res

    # 3. Si el dispositivo esta marcado manualmente como 'restricted' sin politica explicita,
    # verificar si el ultimo estado familiar fue Pausa Temporal o Modo Estudio
    if verdict == "restricted":
        # Si no hubo politica de Estudio que ya permitiera este dominio, bloquear dominios recreativos por seguridad
        if any(_domain_matches(clean_host, d) for d in STUDY_BLOCKED_DOMAINS):
            res = {
                "allowed": False,
                "action_code": "DENY_RESTRICTED_FILTER",
                "reason": f"Acceso supervisado: entretenimiento bloqueado ({clean_host}).",
                "device_name": dev_name,
            }
            _decision_cache[cache_key] = (now_ts, res)
            return res

    res = {
        "allowed": True,
        "action_code": "ALLOW",
        "reason": ev.get("reason") or "Acceso autorizado.",
        "device_name": dev_name,
    }
    _decision_cache[cache_key] = (now_ts, res)
    return res


def _build_blocked_http_response(host: str, reason: str) -> bytes:
    """Construye una respuesta HTTP 403 legible cuando se bloquea una pagina HTTP plana."""
    safe_host = host.replace("<", "").replace(">", "")
    safe_reason = reason.replace("<", "").replace(">", "")
    html = (
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Acceso Pausado | NetGuard Home IP</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#f8fafc;"
        "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}"
        ".card{background:#1e293b;border:1px solid #ef4444;border-radius:16px;padding:24px;max-width:440px}"
        "h1{color:#f87171;font-size:1.2rem;margin:0 0 8px}p{color:#cbd5e1;font-size:.95rem;line-height:1.5}"
        "code{background:#0f172a;padding:2px 6px;border-radius:6px;color:#38bdf8}</style></head>"
        f"<body><div class='card'><h1>Acceso Bloqueado por NetGuard Home IP</h1>"
        f"<p>La conexion hacia <code>{safe_host}</code> fue detenida por el control familiar de tu red.</p>"
        f"<p><strong>Motivo:</strong> {safe_reason}</p></div></body></html>"
    )
    body = html.encode("utf-8")
    headers = (
        "HTTP/1.1 403 Forbidden\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    return headers + body


class _IntermediaryTCPHandler(socketserver.BaseRequestHandler):
    """Manejador TCP por hilo para peticiones HTTP y tuneles HTTPS CONNECT."""

    def _safe_eval(self, client_ip: str, host: str, port: int) -> Dict[str, Any]:
        app = getattr(self.server, "flask_app", None)
        flask_port = getattr(self.server, "flask_port", 5000)
        configured_ips = getattr(self.server, "server_ips", ())
        server_ips = _get_dynamic_server_ips(configured_ips)
        if app is None:
            return {"allowed": True, "action_code": "ALLOW", "reason": "", "device_name": None}
        with app.app_context():
            try:
                return evaluate_proxy_request(
                    client_ip=client_ip,
                    target_host=host,
                    target_port=port,
                    flask_port=flask_port,
                    server_ips=server_ips,
                )
            finally:
                db.session.remove()

    def _tunnel_loop(self, client_sock: socket.socket, remote_sock: socket.socket, client_ip: str, host: str, port: int) -> None:
        """Reenvia bytes bidireccionalmente cortando el tunel al segundo si cambian las reglas."""
        sockets = [client_sock, remote_sock]
        last_ver = get_proxy_policy_version()
        last_check_ts = time.monotonic()

        while True:
            # Si cambio alguna regla en la app o paso 1.2s (para intermitencia/horarios), re-evaluar
            cur_ver = get_proxy_policy_version()
            now_ts = time.monotonic()
            if cur_ver != last_ver or (now_ts - last_check_ts) >= 1.2:
                last_ver = cur_ver
                last_check_ts = now_ts
                decision = self._safe_eval(client_ip, host, port)
                if not decision["allowed"]:
                    _record_proxy_event(client_ip, host, False, decision["action_code"], decision["reason"], decision.get("device_name"))
                    break

            try:
                readable, _, exceptional = select.select(sockets, [], sockets, 0.8)
            except Exception:
                break

            if exceptional:
                break
            if not readable:
                continue

            for sock in readable:
                other = remote_sock if sock is client_sock else client_sock
                try:
                    data = sock.recv(16384)
                except Exception:
                    return
                if not data:
                    return
                try:
                    other.sendall(data)
                except Exception:
                    return

    def handle(self) -> None:
        client_sock: socket.socket = self.request
        client_ip = self.client_address[0]
        client_sock.settimeout(10.0)

        try:
            raw_head = client_sock.recv(8192)
        except Exception:
            return
        if not raw_head:
            return

        header_end = raw_head.find(b"\r\n\r\n")
        if header_end == -1:
            first_part = raw_head
            rest_body = b""
        else:
            first_part = raw_head[:header_end]
            rest_body = raw_head[header_end + 4 :]

        lines = first_part.decode("latin-1", errors="replace").split("\r\n")
        if not lines:
            return
        parts = lines[0].split()
        if len(parts) < 3:
            return

        method, target, version = parts[0].upper(), parts[1], parts[2]
        proxy_port = getattr(self.server, "proxy_port", 8888)
        server_ips = set(_get_dynamic_server_ips(getattr(self.server, "server_ips", ())))

        if method == "CONNECT":
            # Formato CONNECT host:port HTTP/1.1
            if ":" in target:
                host, port_str = target.rsplit(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    port = 443
            else:
                host, port = target, 443

            # Prevenir bucle recursivo hacia el mismo puerto del proxy
            if host.lower() in server_ips and port == proxy_port:
                client_sock.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
                return

            decision = self._safe_eval(client_ip, host, port)
            _record_proxy_event(client_ip, host, decision["allowed"], decision["action_code"], decision["reason"], decision.get("device_name"))

            if not decision["allowed"]:
                client_sock.sendall(b"HTTP/1.1 403 Forbidden\r\nProxy-Agent: NetGuard-Intermediary\r\nConnection: close\r\n\r\n")
                return

            remote_sock = None
            try:
                remote_sock = socket.create_connection((host, port), timeout=8.0)
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                client_sock.settimeout(None)
                remote_sock.settimeout(None)
                self._tunnel_loop(client_sock, remote_sock, client_ip, host, port)
            except Exception:
                try:
                    client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
                except Exception:
                    pass
            finally:
                if remote_sock is not None:
                    try:
                        remote_sock.close()
                    except Exception:
                        pass
        else:
            # Peticion HTTP plana (GET http://host/path HTTP/1.1)
            parsed = urlsplit(target)
            host = parsed.hostname or ""
            port = parsed.port or 80

            if not host:
                for h_line in lines[1:]:
                    if h_line.lower().startswith("host:"):
                        val = h_line.split(":", 1)[1].strip()
                        if ":" in val:
                            host, p_str = val.rsplit(":", 1)
                            try:
                                port = int(p_str)
                            except ValueError:
                                port = 80
                        else:
                            host = val
                        break

            if not host or (host.lower() in server_ips and port == proxy_port):
                client_sock.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
                return

            decision = self._safe_eval(client_ip, host, port)
            _record_proxy_event(client_ip, host, decision["allowed"], decision["action_code"], decision["reason"], decision.get("device_name"))

            if not decision["allowed"]:
                client_sock.sendall(_build_blocked_http_response(host, decision["reason"]))
                return

            # Reconstruir ruta relativa y cabeceras limpias hacia servidor destino
            path = parsed.path or "/"
            if parsed.query:
                path += f"?{parsed.query}"
            rebuilt_lines = [f"{method} {path} {version}"]
            for h_line in lines[1:]:
                low = h_line.lower()
                if low.startswith("proxy-connection:"):
                    continue
                if low.startswith("connection:"):
                    continue
                rebuilt_lines.append(h_line)
            rebuilt_lines.append("Connection: close")
            outbound = ("\r\n".join(rebuilt_lines) + "\r\n\r\n").encode("latin-1") + rest_body

            remote_sock = None
            try:
                remote_sock = socket.create_connection((host, port), timeout=8.0)
                remote_sock.sendall(outbound)
                client_sock.settimeout(None)
                remote_sock.settimeout(None)
                self._tunnel_loop(client_sock, remote_sock, client_ip, host, port)
            except Exception:
                try:
                    client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
                except Exception:
                    pass
            finally:
                if remote_sock is not None:
                    try:
                        remote_sock.close()
                    except Exception:
                        pass


class _ThreadedProxyServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def start_intermediary_proxy_server(
    flask_app,
    host: str = "0.0.0.0",
    port: int = 8888,
    flask_port: int = 5000,
    server_ips: Optional[Tuple[str, ...]] = None,
) -> Optional[socketserver.TCPServer]:
    """
    Inicia en un hilo demonio el servidor Proxy Intermediario HTTP/HTTPS.
    Devuelve la instancia del servidor o None si el puerto ya estaba ocupado.
    """
    global _proxy_server_instance, _proxy_server_port, _proxy_running
    if _proxy_server_instance is not None:
        return _proxy_server_instance

    try:
        server = _ThreadedProxyServer((host, port), _IntermediaryTCPHandler)
        server.flask_app = flask_app  # type: ignore[attr-defined]
        server.flask_port = flask_port  # type: ignore[attr-defined]
        server.proxy_port = port  # type: ignore[attr-defined]
        server.server_ips = tuple(server_ips or ())  # type: ignore[attr-defined]

        thread = threading.Thread(target=server.serve_forever, name="NetGuardProxyIntermediary", daemon=True)
        thread.start()

        _proxy_server_instance = server
        _proxy_server_port = port
        _proxy_running = True
        return server
    except OSError:
        _proxy_running = False
        return None
