"""
Rutas de Consulta de Historial y Auditoría (Solo Lectura).
El historial está protegido frente a modificaciones o eliminaciones desde la interfaz.
"""

import csv
import io
from flask import Blueprint, Response, render_template, request
from flask_login import login_required
from app.extensions import db
from app.models.audit import AuditLog

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.route("/", methods=["GET"])
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    module_filter = (request.args.get("module") or "").strip()
    severity_filter = (request.args.get("severity") or "").strip()
    event_type_filter = (request.args.get("event_type") or "").strip()

    query = AuditLog.query

    if q:
        like_expr = f"%{q}%"
        query = query.filter(
            db.or_(
                AuditLog.description.ilike(like_expr),
                AuditLog.event_type.ilike(like_expr),
                AuditLog.username_snapshot.ilike(like_expr),
                AuditLog.ip_origin.ilike(like_expr),
            )
        )
    if module_filter in AuditLog.MODULE_LABELS:
        query = query.filter(AuditLog.module == module_filter)
    if severity_filter in AuditLog.VALID_SEVERITIES:
        query = query.filter(AuditLog.severity == severity_filter)
    if event_type_filter:
        query = query.filter(AuditLog.event_type == event_type_filter)

    logs = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(200).all()
    distinct_event_types = [
        row[0]
        for row in db.session.query(AuditLog.event_type)
        .distinct()
        .order_by(AuditLog.event_type.asc())
        .all()
    ]

    return render_template(
        "audit/index.html",
        logs=logs,
        q=q,
        module_filter=module_filter,
        severity_filter=severity_filter,
        event_type_filter=event_type_filter,
        distinct_event_types=distinct_event_types,
        audit_Model=AuditLog,
    )


@audit_bp.route("/export.csv", methods=["GET"])
@login_required
def export_csv():
    """Exporta los eventos recientes de auditoría en formato CSV para respaldo documental."""
    logs = AuditLog.query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(500).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Fecha_UTC",
            "Modulo",
            "Severidad",
            "Tipo_Evento",
            "Usuario",
            "IP_Origen",
            "Entidad_Objetivo",
            "ID_Objetivo",
            "Descripcion",
        ]
    )
    for item in logs:
        writer.writerow(
            [
                item.id,
                item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
                item.module,
                item.severity,
                item.event_type,
                item.username_snapshot or "Sistema",
                item.ip_origin or "",
                item.target_type or "",
                item.target_id or "",
                item.description,
            ]
        )

    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=bitacora_auditoria_red_domestica.csv"},
    )

