"""
Pruebas de integración HTTP de vistas, escenario demostrativo de laboratorio,
exportación de auditoría y administración de usuarios.
"""

from tests.conftest import extract_csrf_token


def test_full_web_views_and_demo_seed_workflow(auth_client):
    """Comprueba que todas las vistas principales renderizan sin errores y el flujo Demo funciona."""
    # 1. Configuración y Diagnóstico
    settings_resp = auth_client.get("/settings/")
    assert settings_resp.status_code == 200
    settings_html = settings_resp.get_data(as_text=True)
    assert "Estado de Conexión a Base de Datos" in settings_html
    csrf_token = extract_csrf_token(settings_html)

    # 2. Cargar datos de demostración de laboratorio
    seed_resp = auth_client.post(
        "/settings/seed-demo",
        data={"csrf_token": csrf_token},
        follow_redirects=True,
    )
    assert seed_resp.status_code == 200
    assert "Datos de demostración de laboratorio cargados" in seed_resp.get_data(as_text=True)

    # 3. Verificar Dashboard con los datos de laboratorio
    dash_resp = auth_client.get("/")
    assert dash_resp.status_code == 200
    dash_html = dash_resp.get_data(as_text=True)
    assert "DATOS DE DEMOSTRACIÓN IDENTIFICADOS" in dash_html

    # 4. Verificar listado de Dispositivos, Políticas y Horarios
    assert auth_client.get("/devices/").status_code == 200
    assert auth_client.get("/policies/").status_code == 200
    assert auth_client.get("/schedules/?eval_datetime=2026-10-27T23:15").status_code == 200

    # 5. Exportación CSV de auditoría
    csv_resp = auth_client.get("/audit/export.csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["Content-Type"]
    assert "DEMO_DATA_SEEDED" in csv_resp.get_data(as_text=True)

    # 6. Limpiar datos de demostración
    csrf_token_2 = extract_csrf_token(auth_client.get("/settings/").get_data(as_text=True))
    clear_resp = auth_client.post(
        "/settings/clear-demo",
        data={"csrf_token": csrf_token_2},
        follow_redirects=True,
    )
    assert clear_resp.status_code == 200
    assert "Datos de demostración eliminados" in clear_resp.get_data(as_text=True)

