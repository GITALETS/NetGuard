"""
Punto de entrada principal de la aplicación web.
Proyecto de Tesis:
"Sistema web para administración de dispositivos y políticas de acceso
en redes domésticas mediante gestión de direcciones IP"
"""

import os
from app import create_app
from app.extensions import db

app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)

