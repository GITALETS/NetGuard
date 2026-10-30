# NetGuard Home IP

<p align="center">
  <strong>Sistema web para administración de dispositivos y políticas de acceso en redes domésticas mediante gestión de direcciones IP</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Versión-1.0-blue?style=flat-square" alt="Versión">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Framework-Flask%203.x-black?style=flat-square&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Base%20de%20Datos-MySQL%208.0%2B-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Pruebas-18%20Exitosas-brightgreen?style=flat-square&logo=pytest&logoColor=white" alt="Pytest">
  <img src="https://img.shields.io/badge/Licencia-Proyecto%20de%20Tesis-lightgrey?style=flat-square" alt="Licencia">
</p>

---

## Descripción General

**NetGuard Home IP** es una solución de software orientada a la ciberseguridad defensiva y gestión centralizada de redes domésticas. Permite al administrador del hogar registrar, categorizar y auditar los dispositivos conectados a su red Wi-Fi o Ethernet, gestionando de forma estructurada sus direcciones IP, identificadores físicos (MAC) y perfiles familiares de acceso.

El proyecto está diseñado bajo estándares formales de redes (**RFC 1918**), principios de arquitectura limpia y separación estricta de responsabilidades entre la capa de aplicación, el motor de base de datos relacional y los adaptadores de integración de red.

---

## Cronograma y Estado del Proyecto

El desarrollo del sistema se gestiona de manera continua mediante metodología ágil:
- **Tablero de Seguimiento**: [Cronograma de Desarrollo en GitHub Projects](https://github.com/users/GITALETS/projects/3)

| Módulo del Sistema | Alcance Técnico | Estado |
| :--- | :--- | :---: |
| **Arquitectura Base del Sistema** | Patrón Application Factory, Blueprints modulares, configuración por entornos | **Completado (v1.0)** |
| **Persistencia Relacional (MySQL)** | Esquema relacional DDL, restricciones de integridad, claves foráneas e índices | **Completado (v1.0)** |
| **Autenticación y Seguridad RBAC** | Control de sesiones, hashing criptográfico de contraseñas y protección CSRF | **Completado (v1.0)** |
| **Gestión Centralizada de IPs y Dispositivos** | CRUD completo, validación RFC 1918, subredes CIDR y prevención de duplicidad | **Completado (v1.0)** |
| **Perfiles de Red Familiares** | Segmentación por roles de uso: Familiar, Menor, Visita y Domótica / IoT | **Completado (v1.0)** |
| **Panel de Control (Dashboard)** | Métricas en tiempo real, distribución de dispositivos y estados de conexión | **Completado (v1.0)** |
| **Historial y Auditoría de Seguridad** | Trazabilidad inmutable de eventos de acceso, modificaciones y altas | **Completado (v1.0)** |
| **Políticas de Acceso y Control Parental** | Reglas temporales, permanentes y filtros de navegación configurables | *Fase 2 (En Desarrollo)* |
| **Programación de Horarios Semanales** | Ventanas horarias de acceso con soporte de cruce de medianoche | *Fase 2 (En Desarrollo)* |
| **Adaptador de Integración con Router** | Enlace con hardware de red y simulación de directivas | *Fase 3 (Planificado)* |

---

## Principios Técnicos y Decisiones de Ingeniería

1. **Desacoplamiento de Identificadores de Red**:
   - **Identificador de Sistema (`internal_code`)**: Código alfanumérico único e inmutable (ej. `DEV-0001`).
   - **Dirección Lógica IPv4 (`ip_address`)**: Dirección de red asignada bajo validación rigurosa de pertenencia a subred.
   - **Dirección Física MAC (`mac_address`)**: Identificador de Capa 2 (formato `XX:XX:XX:XX:XX:XX`).
   - **Perfil de Uso (`profile`)**: Categoría funcional (Familiar, Menor, Visita, Domótica/IoT) para aplicación de directivas.

2. **Validación Rigurosa de Direcciones IP (RFC 1918)**:
   - Uso de la biblioteca estándar `ipaddress` para garantizar que toda dirección pertenezca al espacio privado (`192.168.0.0/16`).
   - Validación contra la subred configurada (por defecto `192.168.1.0/24`).
   - Rechazo preventivo de direcciones reservadas: puerta de enlace (`.1`), identificador de red (`.0`) y dirección de difusión broadcast (`.255`).
   - Restricción de unicidad a nivel de esquema (`UNIQUE(network_scope, ip_address)`) para impedir colisiones de direccionamiento.

3. **Ciberseguridad Defensiva y Protección de Datos**:
   - Almacenamiento de contraseñas mediante derivación de claves PBKDF2 con hash SHA-256 (`Werkzeug`).
   - Protección contra falsificación de peticiones en sitios cruzados (**CSRF**) en todos los formularios con mutación de estado.
   - Cookies de sesión endurecidas con flags `HttpOnly` y `SameSite=Lax`.
   - Registro de auditoría sanitizado para evitar almacenamiento de parámetros sensibles.

---

## Tecnologías Empleadas

- **Backend**: Python 3.10+ / 3.14, Flask 3.x
- **Capa ORM / Datos**: SQLAlchemy 2.x, Flask-SQLAlchemy 3.x
- **Conector de Base de Datos**: PyMySQL 1.1+
- **Motor de Base de Datos**: MySQL 8.0+ / MariaDB 10.5+ / MySQL Workbench
- **Seguridad**: Flask-Login, Flask-WTF, Werkzeug Security
- **Frontend**: HTML5 Semántico, Tailwind CSS, Iconografía Vectorial SVG
- **Pruebas Automatizadas**: Pytest 8.x

---

## Estructura de la Arquitectura

```text
├── app/
│   ├── models/            # Modelos de entidad relacional (User, Device, AuditLog)
│   ├── routes/            # Controladores modularizados mediante Flask Blueprints
│   ├── services/          # Capa de lógica de negocio y validadores de red
│   ├── static/            # Recursos estáticos (estilos CSS y scripts modulares)
│   ├── templates/         # Vistas HTML5 responsivas con diseño libre de fatiga visual
│   ├── extensions.py      # Instanciación centralizada de extensiones (db, login, csrf)
│   └── __init__.py        # Fábrica de aplicaciones (Application Factory Pattern)
├── database/
│   ├── schema_avance1.sql # Script DDL relacional para inicialización en MySQL Workbench
│   └── schema.sql         # Esquema relacional proyectado con fases complementarias
├── tests/                 # Suite de pruebas automatizadas unitarias y de integración
├── config.py              # Gestión centralizada de entornos (Desarrollo, Pruebas, Producción)
├── requirements.txt       # Manifiesto de dependencias de Python
└── run.py                 # Punto de entrada para ejecución del servidor
```

---

## Instalación y Puesta en Marcha

### 1. Clonar el Repositorio
```bash
git clone https://github.com/GITALETS/NetGuard.git
cd NetGuard
```

### 2. Crear y Activar el Entorno Virtual
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar la Base de Datos en MySQL
1. En **MySQL Workbench**, abra el archivo `database/schema_avance1.sql`.
2. Ejecute el script para crear la base de datos `red_domestica_tesis` y las tablas correspondientes.

### 5. Configurar Variables de Entorno
Cree un archivo de configuración `.env` en la raíz del proyecto tomando como base los siguientes parámetros:
```ini
FLASK_APP=run.py
FLASK_DEBUG=1
SECRET_KEY=clave_secreta_de_demostracion
DATABASE_URL=mysql+pymysql://usuario_mysql:password_mysql@localhost:3306/red_domestica_tesis
DEFAULT_NETWORK_SCOPE=192.168.1.0/24
DEFAULT_GATEWAY_IP=192.168.1.1
```

### 6. Inicializar Usuario Administrador
```bash
flask init-admin --username admin --email admin@red-domestica.local --password TuPassword123! --full-name "Administrador de Red"
```

### 7. Ejecutar la Aplicación
```bash
python run.py
```
Acceda a la interfaz web desde: **`http://127.0.0.1:5000`**

---

## Pruebas Automatizadas

El proyecto cuenta con una batería completa de pruebas que verifican validaciones de IP, unicidad, flujos de autenticación, control de accesos y persistencia relacional:

```bash
pytest -v
```

Resultado verificado:
```text
tests/test_audit_and_db_errors.py ........ PASSED
tests/test_auth.py ....................... PASSED
tests/test_devices.py .................... PASSED
tests/test_policies.py .................. PASSED
tests/test_schedules.py ................. PASSED
tests/test_views_and_seed.py ............. PASSED

18 passed in 5.72s
```
