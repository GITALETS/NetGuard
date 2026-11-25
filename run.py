"""
Punto de entrada principal de la aplicación web.
Proyecto de Tesis:
"Sistema web para administración de dispositivos y políticas de acceso
en redes domésticas mediante gestión de direcciones IP"
"""

import os
from app import create_app
from app.extensions import db
from app.services.network_probe_service import detect_local_network_info

app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # Escuchar en todas las interfaces (0.0.0.0) por defecto para permitir acceso
    # desde teléfonos y tabletas conectados al mismo módem o mini-módem Wi-Fi.
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"

    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        net_info = detect_local_network_info(port=port)
        print("\n============================================================")
        print(" NetGuard Home IP - Accesos de Red Activos")
        print(f" - PC Local      : http://127.0.0.1:{port}")
        if net_info.get("is_lan_reachable"):
            print(f" - Telefono WiFi : {net_info['mobile_url']}")
            print(f" - Portal Cliente: {net_info['client_status_url']}")
            print(f" - Subred Activa : {net_info['network_scope']} (Gateway: {net_info['gateway_ip']})")
        print("============================================================\n")

    app.run(host=host, port=port, debug=debug)
