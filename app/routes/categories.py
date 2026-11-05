"""
Rutas para la Administración de Categorías Dinámicas del Sistema.
Permite a Administradores y Superadministradores crear nuevas categorías
de dispositivos, perfiles de red y destinos de filtrado.
"""

from flask import Blueprint, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required
from app.routes.decorators import admin_required
from app.services.category_service import create_custom_category, get_categories_by_type
from app.services.validators import ValidationError

categories_bp = Blueprint("categories", __name__, url_prefix="/categories")


@categories_bp.route("/quick-add", methods=["POST"])
@login_required
@admin_required
def quick_add():
    """
    Endpoint para alta rápida de categorías dinámicas desde formularios web.
    Soporta tanto peticiones AJAX (JSON) como envíos de formularios tradicionales.
    """
    is_json = request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if request.is_json:
        data = request.get_json() or {}
        category_type = data.get("category_type", "")
        name = data.get("name", "")
        description = data.get("description", "")
        code = data.get("code")
    else:
        category_type = request.form.get("category_type", "")
        name = request.form.get("name", "")
        description = request.form.get("description", "")
        code = request.form.get("code")

    try:
        new_cat = create_custom_category(
            category_type=category_type,
            name=name,
            description=description,
            code=code,
            created_by_id=current_user.id,
        )

        if is_json:
            return jsonify({
                "success": True,
                "message": f"Categoría '{new_cat.name}' registrada correctamente.",
                "category": {
                    "id": new_cat.id,
                    "type": new_cat.category_type,
                    "code": new_cat.code,
                    "name": new_cat.name,
                    "description": new_cat.description,
                },
            }), 201

        flash(f"Categoría '{new_cat.name}' registrada con éxito.", "success")
        return redirect(request.referrer or url_for("devices.index"))

    except ValidationError as exc:
        if is_json:
            return jsonify({"success": False, "error": str(exc)}), 400
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("devices.index"))

