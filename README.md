# Sistema web para administración de dispositivos y políticas de acceso en redes domésticas mediante gestión de direcciones IP

## Documento de Entrega: Primer Avance Funcional (35% del Sistema)
**Carrera**: Ingeniería en Sistemas Computacionales  
**Nivel del Proyecto**: Prototipo Funcional de Tesis Universitaria — Fase 1  
**Repositorio de Evidencia**: Git / GitHub  

---

## 1. Ficha Técnica y Alcance del Avance 1 (35%)

En cumplimiento con el cronograma de trabajo de titulación, este primer avance presenta la **arquitectura base**, el **modelado y persistencia en base de datos relacional (MySQL)**, el **módulo de autenticación y seguridad** y el **núcleo central del sistema: la administración de dispositivos y gestión de direcciones IP en la red doméstica**.

### Resumen del Cumplimiento por Fases

| Módulo del Sistema | Alcance Previsto | Estado en este Avance (35%) |
| :--- | :--- | :--- |
| **Arquitectura de Software** | Patrón Application Factory, Blueprints, Servicios y Validadores | **100% Completado** |
| **Base de Datos Relacional** | Esquema DDL en MySQL 8.0+, tipos de datos, llaves e índices | **100% Completado** |
| **Autenticación y Sesiones** | Login, Logout, contraseñas hasheadas (Werkzeug), CSRF, roles RBAC | **100% Completado** |
| **Administración de Dispositivos e IPs** | CRUD completo, validación IPv4 (RFC 1918), subred CIDR, MAC y prevención de duplicados | **100% Completado** |
| **Panel / Dashboard de Dispositivos** | Métricas de equipos, distribución visual y listado rápido | **100% Completado** |
| **Auditoría e Historial Base** | Registro inmutable de eventos de acceso y cambios en dispositivos | **100% Completado** |
| **Políticas de Acceso y Restricciones** | Definición de políticas temporales, permanentes y filtros | *Programado: Fase 2 (Siguiente Entrega)* |
| **Horarios de Acceso Semanal** | Programación por franjas horarias y cruce de medianoche | *Programado: Fase 2 (Siguiente Entrega)* |
| **Adaptador de Router / Enlace** | Integración simulada o física con equipos de red | *Programado: Fase 3 (Entrega Final)* |

---

## 2. Decisiones Técnicas y Rigor de Ingeniería

Para este proyecto universitario se aplicaron principios de ingeniería de software y ciberseguridad defensiva:

1. **Distinción entre identificadores**:
   - Una **dirección IP** no identifica permanentemente a un dispositivo (puede cambiar por expiración de concesión DHCP).
   - Se distingue entre:
     - `internal_code`: Identificador único inmutable del sistema (ej. `DEV-A1B2C3`).
     - `name`: Nombre amigable para el usuario doméstico (ej. *Laptop de Papá*).
     - `ip_address`: Dirección IPv4 validada rigurosamente con la biblioteca estándar `ipaddress`.
     - `mac_address`: Dirección física de capa de enlace (formato `XX:XX:XX:XX:XX:XX`).
2. **Validaciones de Red**:
   - Validación de direcciones IPv4 privadas según **RFC 1918** y pertenencia estricta a la subred doméstica configurada (por defecto `192.168.1.0/24`).
   - Detección y rechazo de direcciones de red (`.0`), de broadcast (`.255`), de loopback (`127.0.0.1`) o la dirección reservada para la puerta de enlace (`192.168.1.1`).
   - Prevención a nivel de aplicación y de base de datos (`UNIQUE(network_scope, ip_address)`) de colisiones o duplicidad de direcciones IP.
3. **Seguridad y Ciberseguridad Defensiva**:
   - Hashing criptográfico de contraseñas mediante PBKDF2/SHA-256 (`werkzeug.security`).
   - Tokens CSRF en todos los formularios con mutación de estado.
   - Headers y cookies de sesión configuradas con directivas `HttpOnly` y `SameSite=Lax`.
   - Sanitización de contraseñas y datos sensibles en los registros de auditoría y diagnósticos.

---

## 3. Pila Tecnológica Implementada

- **Lenguaje**: Python 3.10+ / 3.14
- **Framework Web**: Flask 3.x
- **ORM / Acceso a Datos**: SQLAlchemy 2.x / Flask-SQLAlchemy 3.x
- **Controlador de Base de Datos**: PyMySQL 1.1+
- **Gestor de Base de Datos**: MySQL 8.0+ / MariaDB 10.5+ / MySQL Workbench
- **Gestión de Sesiones**: Flask-Login 0.6+
- **Seguridad y Formularios**: Flask-WTF / WTForms / Werkzeug
- **Frontend**: HTML5 Semántico, Tailwind CSS y componentes con Iconos SVG vectoriales (sin emojis, diseño accesible para familias con modos Claro y Oscuro suave).
- **Control de Versiones**: Git y GitHub

---

## 4. Estructura del Proyecto

```text
TESISAVANCE/
├── app/
│   ├── models/            # Modelos SQLAlchemy (User, Device, AuditLog)
│   ├── routes/            # Controladores (auth, dashboard, devices, users, settings, audit)
│   ├── services/          # Lógica de negocio (validadores de red, servicio de dispositivos)
│   ├── static/            # Hojas de estilo Tailwind (CSS) y JavaScript modular
│   ├── templates/         # Plantillas HTML con diseño responsivo e iconos SVG
│   ├── extensions.py      # Instancias de db, login_manager, csrf
│   └── __init__.py        # Application Factory
├── database/
│   ├── schema_avance1.sql # Script DDL listo para ejecutar en MySQL Workbench (Avance 1)
│   └── schema.sql         # Esquema completo proyectado para Fases 2 y 3
├── tests/                 # Pruebas automatizadas con pytest
├── .env.example           # Plantilla de variables de entorno sin secretos
├── .gitignore             # Exclusión de archivos sensibles y entornos (.env, .venv, *.db)
├── config.py              # Configuraciones de desarrollo, pruebas y producción
├── requirements.txt       # Dependencias del proyecto
├── run.py                 # Punto de entrada de la aplicación
└── README.md              # Documentación oficial del avance
```

---

## 5. Instrucciones de Puesta en Marcha

### Paso 1: Configurar la Base de Datos en MySQL Workbench
1. Abre **MySQL Workbench** y conéctate a tu instancia local de MySQL.
2. Abre el archivo [`database/schema_avance1.sql`](database/schema_avance1.sql).
3. Presiona el botón del rayo (**Execute**) para crear la base de datos `red_domestica_tesis` y las tablas del primer avance (`users`, `devices`, `audit_logs`).

### Paso 2: Crear el Entorno Virtual e Instalar Dependencias
En la terminal de Visual Studio Code:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Paso 3: Configurar el archivo `.env`
Copia `.env.example` como `.env` y verifica los datos de tu MySQL local:
```env
SECRET_KEY=clave_secreta_tesis_avance1_2026
DATABASE_URL=mysql+pymysql://root:TU_PASSWORD@localhost:3306/red_domestica_tesis
DEFAULT_NETWORK_SCOPE=192.168.1.0/24
DEFAULT_GATEWAY_IP=192.168.1.1
```

### Paso 4: Inicializar el Usuario Administrador y Ejecutar
Crea el usuario inicial mediante el comando seguro del CLI:
```powershell
.\.venv\Scripts\python.exe -m flask init-db --admin-user admin --admin-email admin@red-domestica.local --admin-pass Admin1234!
```

Inicia el servidor web:
```powershell
.\.venv\Scripts\python.exe run.py
```
Abre tu navegador en: **`http://127.0.0.1:5000`**  
Credenciales iniciales:
- **Usuario**: `admin`
- **Contraseña**: `Admin1234!`

---

## 6. Pruebas Automatizadas (Evidencia de Calidad de Software)
Para ejecutar la suite de pruebas unitarias y de integración:
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 7. Instrucciones para Subir a GitHub como Evidencia

1. Abre tu cuenta en [GitHub.com](https://github.com) y crea un nuevo repositorio llamado:  
   `tesis-red-domestica-administracion-ip` (puedes elegirlo público o privado según la normativa de tu universidad).
2. En la terminal de esta carpeta, ejecuta:
```powershell
git init
git add .
git commit -m "Primer Avance de Tesis (35%): Arquitectura, Base de Datos MySQL, Autenticación y Gestión de Dispositivos e IPs"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/tesis-red-domestica-administracion-ip.git
git push -u origin main
```
> **Nota de Seguridad**: Gracias al archivo `.gitignore` incluido, tu contraseña de MySQL y tus secretos locales de `.env` **nunca se subirán a GitHub**, protegiendo la seguridad de tu entorno.
