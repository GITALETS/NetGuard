"""
Pruebas automatizadas del Monitor de Red en Vivo, Detección LAN/QR,
Evaluación por IP en Tiempo Real y Vistas Móviles.
"""

from datetime import datetime, timedelta
from app.models.user import utc_now_naive
from app.services.device_service import create_device
from app.services.network_probe_service import detect_local_network_info, evaluate_live_device_access
from app.services.policy_service import create_policy
from app.services.schedule_service import create_schedule
from tests.conftest import extract_csrf_token


def test_detect_local_network_info_structure():
    """Verifica que la detección automática de red devuelva estructura completa sin fallos."""
    info = detect_local_network_info(port=5000)
    assert "local_ip" in info
    assert "network_scope" in info
    assert "scan_cidr" in info
    assert "gateway_ip" in info
    assert "mobile_url" in info
    assert "client_status_url" in info
    assert info["port"] == 5000


def test_evaluate_live_device_access_hierarchy_and_intermittency(app, admin_user):
    """Comprueba evaluación en vivo por IP: sin registro, autorizado, bloqueado, horario global e intermitencia."""
    with app.app_context():
        # 1. IP no registrada
        unreg = evaluate_live_device_access("192.168.8.99")
        assert unreg["found"] is False
        assert unreg["verdict_code"] == "unregistered"

        # 2. Dispositivo autorizado + política con intermitencia (10 min activo / 5 min pausa)
        dev_phone = create_device(
            {
                "name": "Celular Demo",
                "ip_address": "192.168.8.40",
                "network_scope": "192.168.8.0/24",
                "device_type": "smartphone",
                "admin_status": "authorized",
            },
            user_id=admin_user,
        )

        # Sin políticas ni horarios -> allowed
        base_eval = evaluate_live_device_access("192.168.8.40")
        assert base_eval["found"] is True
        assert base_eval["verdict_code"] == "allowed"

        # Crear política intermitente iniciada hace exactamente 12 minutos en UTC
        now_utc = utc_now_naive()
        start_utc = now_utc - timedelta(minutes=12)
        create_policy(
            {
                "name": "Control YouTube",
                "device_id": dev_phone.id,
                "policy_type": "intermittent_intermediary",
                "action": "restrict",
                "priority": 10,
                "valid_from": start_utc.strftime("%Y-%m-%d %H:%M"),
                "target_scope": "specific_domain",
                "target_domain": "youtube.com",
                "is_intermittent": True,
                "interval_active_minutes": 10,
                "interval_pause_minutes": 5,
            },
            user_id=admin_user,
        )

        # A los 12 minutos (de ciclo 10 activo + 5 pausa) debe caer en fase de pausa
        eval_pause = evaluate_live_device_access(
            "192.168.8.40",
            utc_ref_dt=start_utc + timedelta(minutes=12),
        )
        assert eval_pause["verdict_code"] == "intermittent_pause"
        assert eval_pause["intermittent_status"]["phase"] == "pause_window"
        assert eval_pause["intermittent_status"]["target"] == "youtube.com"

        # A los 4 minutos del inicio debe caer en ventana activa
        eval_active = evaluate_live_device_access(
            "192.168.8.40",
            utc_ref_dt=start_utc + timedelta(minutes=4),
        )
        assert eval_active["verdict_code"] == "restricted"
        assert eval_active["intermittent_status"]["phase"] == "active_window"

        # 3. Horario global restringido vs equipo bloqueado
        dev_blocked = create_device(
            {
                "name": "Equipo Bloqueado",
                "ip_address": "192.168.8.41",
                "network_scope": "192.168.8.0/24",
                "device_type": "tablet",
                "admin_status": "blocked",
            },
            user_id=admin_user,
        )
        create_schedule(
            {
                "label": "Pausa General Cena",
                "device_id": "all",
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "start_time": "00:00",
                "end_time": "23:59",
                "window_behavior": "restricted_window",
                "is_active": True,
            },
            user_id=admin_user,
        )
        # El equipo autorizado entra en pausa por horario global
        eval_sched = evaluate_live_device_access("192.168.8.40", local_ref_dt=datetime(2026, 11, 25, 18, 0))
        assert eval_sched["verdict_code"] == "schedule_paused"

        # El equipo bloqueado mantiene su estado 'blocked' sin dejarse anular por horarios globales
        eval_blk = evaluate_live_device_access("192.168.8.41", local_ref_dt=datetime(2026, 11, 25, 18, 0))
        assert eval_blk["verdict_code"] == "blocked"
        assert dev_blocked.admin_status == "blocked"


def test_network_routes_and_mobile_client_portal(client, auth_client, monkeypatch):
    """Comprueba las rutas HTTP del Monitor en Vivo, portal móvil público /mi-acceso y prellenado de dispositivo."""
    # Portal público accesible desde otro celular sin sesión
    public_resp = client.get("/network/mi-acceso")
    assert public_resp.status_code == 200
    assert "Verificación en Vivo por IP" in public_resp.get_data(as_text=True)

    api_resp = client.get("/network/api/evaluate")
    assert api_resp.status_code == 200
    assert api_resp.get_json()["success"] is True

    # Monitor autenticado
    mon_resp = auth_client.get("/network/")
    assert mon_resp.status_code == 200
    mon_html = mon_resp.get_data(as_text=True)
    assert "Monitor en Vivo y Acceso Móvil" in mon_html
    assert "mobile-bottom-nav" in mon_html

    csrf_token = extract_csrf_token(mon_html)

    # Simular respuesta determinista de ping para evitar dependencia de latencia de red en pruebas
    monkeypatch.setattr(
        "app.routes.network.ping_host",
        lambda ip, timeout_ms=900: {
            "ip_address": ip,
            "online": True,
            "latency_ms": 12.5,
            "detail": "En línea (respuesta ICMP en 12.5 ms)",
            "checked_at": "12:00:00",
        },
    )
    ping_resp = auth_client.post(
        "/network/ping",
        json={"ip_address": "192.168.8.25"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert ping_resp.status_code == 200
    ping_json = ping_resp.get_json()
    assert ping_json["online"] is True
    assert ping_json["latency_ms"] == 12.5

    # Prellenado automático al abrir /devices/new desde escáner Wi-Fi
    prefill_resp = auth_client.get(
        "/devices/new?ip=192.168.8.33&mac=AA:BB:CC:DD:EE:11&scope=192.168.8.0/24&name=Celular%20Invitado"
    )
    assert prefill_resp.status_code == 200
    prefill_html = prefill_resp.get_data(as_text=True)
    assert "192.168.8.33" in prefill_html
    assert "192.168.8.0/24" in prefill_html
    assert "Celular Invitado" in prefill_html


def test_intermediary_proxy_decision_engine(app, auth_client):
    """Verifica las decisiones reales del Proxy Intermediario por IP, Modo Estudio, Bloqueo e Intermitencia."""
    from app.services.intermediary_proxy import bump_proxy_policy_version, evaluate_proxy_request

    with app.app_context():
        dev = create_device(
            {
                "name": "Android Proxy Demo",
                "ip_address": "172.20.10.9",
                "network_scope": "172.20.10.0/28",
                "device_type": "smartphone",
                "admin_status": "authorized",
            }
        )
        dev_id = dev.id
        bump_proxy_policy_version()

        # 1. Autorizado: permite todo
        assert evaluate_proxy_request("172.20.10.9", "www.youtube.com")["allowed"] is True
        assert evaluate_proxy_request("172.20.10.9", "es.wikipedia.org")["allowed"] is True

        # 2. Bloqueado: corta internet real pero mantiene acceso a NetGuard local
        dev.admin_status = "blocked"
        from app.extensions import db
        db.session.commit()
        bump_proxy_policy_version()

        assert evaluate_proxy_request("172.20.10.9", "www.youtube.com")["allowed"] is False
        assert evaluate_proxy_request("172.20.10.9", "www.google.com")["allowed"] is False
        assert evaluate_proxy_request("172.20.10.9", "172.20.10.4", target_port=5000, server_ips=("172.20.10.4",))["allowed"] is True

    # 3. Modo Estudio vía Control Familiar: bloquea YouTube/TikTok pero permite Wikipedia
    detail_resp = auth_client.get(f"/devices/{dev_id}")
    csrf_tok = extract_csrf_token(detail_resp.get_data(as_text=True))
    auth_client.post(
        f"/devices/{dev_id}/family-access",
        data={"csrf_token": csrf_tok, "mode": "study"},
        follow_redirects=True,
    )

    with app.app_context():
        assert evaluate_proxy_request("172.20.10.9", "m.youtube.com")["allowed"] is False
        assert evaluate_proxy_request("172.20.10.9", "rr3---sn.googlevideo.com")["allowed"] is False
        assert evaluate_proxy_request("172.20.10.9", "www.tiktok.com")["allowed"] is False
        assert evaluate_proxy_request("172.20.10.9", "es.wikipedia.org")["allowed"] is True

    # 4. Pausa Temporal vía Control Familiar: detiene todo Internet
    auth_client.post(
        f"/devices/{dev_id}/family-access",
        data={"csrf_token": csrf_tok, "mode": "pause"},
        follow_redirects=True,
    )
    with app.app_context():
        assert evaluate_proxy_request("172.20.10.9", "www.google.com")["allowed"] is False
        assert evaluate_proxy_request("172.20.10.9", "es.wikipedia.org")["allowed"] is False

