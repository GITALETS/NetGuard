"""
Servicio para la administración de Categorías Dinámicas del Sistema.
Provee operaciones para registrar, consultar y validar tipos de dispositivos,
perfiles familiares y categorías de filtrado creados por Administradores y Superadministradores.
"""

import re
from typing import Dict, List, Optional
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.extensions import db
from app.models.category import SystemCategory
from app.models.device import Device
from app.services.audit_service import log_audit_event
from app.services.validators import ValidationError

CATEGORY_CODE_RE = re.compile(r"^[a-z0-9_]{2,40}$")


def get_categories_by_type(category_type: str) -> List[SystemCategory]:
    """
    Recupera todas las categorías registradas para un tipo específico,
    ordenadas priorizando las predeterminadas y alfabéticamente por nombre.
    """
    if category_type not in SystemCategory.VALID_CATEGORY_TYPES:
        raise ValidationError(f"Tipo de categoría inválido: '{category_type}'.")
    return (
        SystemCategory.query.filter_by(category_type=category_type)
        .order_by(SystemCategory.is_system_default.desc(), SystemCategory.name.asc())
        .all()
    )


def get_category_options(category_type: str) -> Dict[str, str]:
    """
    Devuelve un diccionario {code: name} de categorías para poblar selectores en formularios.
    Combina las opciones por defecto del modelo con las categorías personalizadas en base de datos.
    """
    categories = get_categories_by_type(category_type)
    options: Dict[str, str] = {}
    for cat in categories:
        options[cat.code] = cat.name
    return options


def create_custom_category(
    category_type: str,
    name: str,
    description: Optional[str] = None,
    code: Optional[str] = None,
    created_by_id: Optional[int] = None,
) -> SystemCategory:
    """
    Crea una nueva categoría dinámica en el sistema.
    Requiere nombre descriptivo y genera automáticamente un código slug si no se especifica.
    """
    clean_type = (category_type or "").strip()
    clean_name = (name or "").strip()
    clean_desc = (description or "").strip() or None

    if clean_type not in SystemCategory.VALID_CATEGORY_TYPES:
        raise ValidationError(f"Tipo de categoría inválido: '{clean_type}'.")

    if not clean_name or len(clean_name) < 2 or len(clean_name) > 100:
        raise ValidationError("El nombre de la categoría debe tener entre 2 y 100 caracteres.")

    # Generar código slug normalizado si no se provee
    if not code:
        generated_code = re.sub(r"[^a-z0-9]+", "_", clean_name.lower()).strip("_")
        clean_code = generated_code[:40]
    else:
        clean_code = code.strip().lower()

    if not CATEGORY_CODE_RE.match(clean_code):
        raise ValidationError(
            f"El código identificador '{clean_code}' debe contener entre 2 y 40 caracteres (minúsculas, números y guión bajo)."
        )

    # Validar duplicados para el mismo tipo
    existing = SystemCategory.query.filter_by(category_type=clean_type, code=clean_code).first()
    if existing:
        raise ValidationError(
            f"Ya existe una categoría de tipo '{clean_type}' con el identificador '{clean_code}'."
        )

    new_cat = SystemCategory(
        category_type=clean_type,
        code=clean_code,
        name=clean_name,
        description=clean_desc,
        is_system_default=False,
        created_by_id=created_by_id,
    )

    try:
        db.session.add(new_cat)
        db.session.flush()

        log_audit_event(
            event_type="CATEGORY_CREATED",
            module="system",
            description=f"Alta de categoría dinámica '{new_cat.name}' [{new_cat.type_label}] con código '{new_cat.code}'.",
            severity="info",
            user_id=created_by_id,
            target_type="category",
            target_id=new_cat.id,
            metadata={"category_type": clean_type, "code": clean_code, "name": clean_name},
        )
        db.session.commit()
        return new_cat
    except IntegrityError as exc:
        db.session.rollback()
        raise ValidationError("El identificador de categoría ya está en uso.") from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ValidationError("Error al persistir la categoría en la base de datos.") from exc


def seed_default_system_categories() -> int:
    """
    Puebla de manera idempotente los tipos de dispositivos, perfiles y categorías
    predeterminadas del sistema en la tabla `system_categories`.
    """
    # 1. Tipos de Dispositivo predeterminados
    default_device_types = [
        ("workstation", "PC de Escritorio / Estación", "Computadoras de escritorio de alta potencia"),
        ("laptop", "Computadora Portátil", "Laptops y equipos móviles de cómputo"),
        ("smartphone", "Teléfono Inteligente", "Teléfonos móviles de la familia y visitas"),
        ("tablet", "Tableta", "Tabletas electrónicas infantiles o generales"),
        ("iot", "Dispositivo IoT / Domótica", "Sensores, cámaras de seguridad y enchufes inteligentes"),
        ("smart_tv", "Smart TV / Multimedia", "Televisores inteligentes, pantallas y dongles de streaming"),
        ("console", "Consola de Videojuegos", "Dispositivos de entretenimiento de videojuegos"),
        ("server", "Servidor Local / NAS", "Almacenamiento en red o servidores de pruebas"),
        ("printer", "Impresora de Red", "Impresoras y multifuncionales conectados por red"),
        ("other", "Otro Dispositivo", "Equipos diversos o no categorizados"),
    ]

    # 2. Perfiles Familiares de Red predeterminados
    default_profiles = [
        ("family", "Familiar (Adultos / General)", "Acceso general para los miembros adultos del hogar"),
        ("child", "Menor (Niños / Estudiantes con supervisión)", "Perfiles de hijos o menores con horarios y control parental"),
        ("guest", "Visita (Invitados temporales)", "Dispositivos temporales de visitas que requieren aislamiento"),
        ("iot", "Hogar Inteligente / IoT (Smart TV, Cámaras)", "Equipos inteligentes con permisos exclusivos a sus servicios"),
        ("other", "Otro Perfil", "Perfiles personalizados"),
    ]

    # 3. Categorías de Navegación / Destinos de Filtrado predeterminados
    default_policy_targets = [
        ("social_media", "Redes Sociales", "Sitios como Facebook, Instagram, TikTok y X"),
        ("video_streaming", "Streaming de Video", "Plataformas como YouTube, Netflix y Twitch"),
        ("gaming_servers", "Servidores de Videojuegos", "Plataformas como Roblox, Steam y PlayStation Network"),
        ("educational_content", "Contenido Educativo y Académico", "Portales escolares, bibliotecas y plataformas de estudio"),
        ("general_browsing", "Navegación General", "Tráfico web habitual sin categoría específica"),
    ]

    # 4. Estados y Permisos Administrativos de Acceso
    default_admin_statuses = [
        ("authorized", "Autorizado", "Dispositivo plenamente permitido para navegar"),
        ("restricted", "Restringido (Con Políticas)", "Dispositivo sujeto a reglas o descansos programados"),
        ("blocked", "Bloqueado / No Autorizado", "Dispositivo sin acceso a la red"),
        ("pending", "Pendiente de Revisión", "Dispositivo recién conectado en espera de verificación"),
    ]

    created = 0

    for code, name, desc in default_device_types:
        if not SystemCategory.query.filter_by(category_type="device_type", code=code).first():
            db.session.add(
                SystemCategory(
                    category_type="device_type",
                    code=code,
                    name=name,
                    description=desc,
                    is_system_default=True,
                )
            )
            created += 1

    for code, name, desc in default_profiles:
        if not SystemCategory.query.filter_by(category_type="device_profile", code=code).first():
            db.session.add(
                SystemCategory(
                    category_type="device_profile",
                    code=code,
                    name=name,
                    description=desc,
                    is_system_default=True,
                )
            )
            created += 1

    for code, name, desc in default_policy_targets:
        if not SystemCategory.query.filter_by(category_type="policy_target", code=code).first():
            db.session.add(
                SystemCategory(
                    category_type="policy_target",
                    code=code,
                    name=name,
                    description=desc,
                    is_system_default=True,
                )
            )
            created += 1

    for code, name, desc in default_admin_statuses:
        if not SystemCategory.query.filter_by(category_type="admin_status", code=code).first():
            db.session.add(
                SystemCategory(
                    category_type="admin_status",
                    code=code,
                    name=name,
                    description=desc,
                    is_system_default=True,
                )
            )
            created += 1

    if created > 0:
        db.session.commit()

    return created

