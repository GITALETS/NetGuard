"""
Inicialización centralizada de extensiones de Flask.
"""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor, inicie sesión para acceder al panel de administración."
login_manager.login_message_category = "warning"
login_manager.session_protection = "strong"

