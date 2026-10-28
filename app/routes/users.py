"""
Rutas de Administración de Usuarios Autorizados del Sistema.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models.user import User
from app.routes.decorators import admin_required
from app.services.user_service import create_user, update_user_account
from app.services.validators import ValidationError

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/")
@login_required
@admin_required
def index():
    users = User.query.order_by(User.created_at.asc()).all()
    return render_template("users/index.html", users=users, user_Model=User)


@users_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form_data = {
        "username": "",
        "email": "",
        "full_name": "",
        "role": "operator",
        "is_active": True,
    }
    if request.method == "POST":
        form_data = {
            "username": request.form.get("username", ""),
            "email": request.form.get("email", ""),
            "full_name": request.form.get("full_name", ""),
            "role": request.form.get("role", "operator"),
            "is_active": request.form.get("is_active") == "1",
        }
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if password != password_confirm:
            flash("Las contraseñas ingresadas no coinciden.", "error")
            return render_template("users/form.html", target_user=None, form_data=form_data, user_Model=User), 400

        try:
            new_user = create_user(
                username=form_data["username"],
                email=form_data["email"],
                full_name=form_data["full_name"],
                password=password,
                role=form_data["role"],
                is_active=form_data["is_active"],
                actor_user_id=current_user.id,
            )
            flash(f"Usuario '{new_user.username}' creado correctamente.", "success")
            return redirect(url_for("users.index"))
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_template("users/form.html", target_user=None, form_data=form_data, user_Model=User), 400

    return render_template("users/form.html", target_user=None, form_data=form_data, user_Model=User)


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit(user_id: int):
    target_user = db.get_or_404(User, user_id)
    form_data = {
        "username": target_user.username,
        "email": target_user.email,
        "full_name": target_user.full_name,
        "role": target_user.role,
        "is_active": target_user.is_active,
    }

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        new_password_confirm = request.form.get("new_password_confirm", "")
        form_data = {
            "username": target_user.username,
            "email": request.form.get("email", ""),
            "full_name": request.form.get("full_name", ""),
            "role": request.form.get("role", target_user.role),
            "is_active": request.form.get("is_active") == "1",
            "new_password": new_password,
        }

        if new_password and new_password != new_password_confirm:
            flash("La confirmación de la nueva contraseña no coincide.", "error")
            return render_template("users/form.html", target_user=target_user, form_data=form_data, user_Model=User), 400

        try:
            update_user_account(target_user, form_data, actor_user=current_user)
            flash(f"Cuenta de usuario '{target_user.username}' actualizada.", "success")
            return redirect(url_for("users.index"))
        except ValidationError as exc:
            flash(str(exc), "error")
            return render_template("users/form.html", target_user=target_user, form_data=form_data, user_Model=User), 400

    return render_template("users/form.html", target_user=target_user, form_data=form_data, user_Model=User)

