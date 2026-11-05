# NetGuard Home IP

<p align="center">
  <strong>Sistema web para administración de dispositivos y políticas de acceso en redes domésticas mediante gestión de direcciones IP</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Framework-Flask%203.x-black?style=flat-square&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Base%20de%20Datos-MySQL%208.0%2B-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Pruebas-23%20Exitosas-brightgreen?style=flat-square&logo=pytest&logoColor=white" alt="Pytest">
  <img src="https://img.shields.io/badge/Licencia-Proyecto%20de%20Tesis-lightgrey?style=flat-square" alt="Licencia">
</p>

---

## 1. Descripcion General del Proyecto

NetGuard Home IP es una plataforma de software orientada a la gestion de ciberseguridad defensiva, direccionamiento logico y administracion de politicas de acceso en redes locales residenciales.

En los entornos familiares modernos convergen multiples tipos de tecnologias: computadoras de trabajo, telefonos moviles, tabletas de menores de edad, pantallas inteligentes, consolas de videojuegos y dispositivos de Internet de las Cosas (IoT). La mayoria de los enrutadores comerciales carecen de una interfaz intuitiva y centralizada para auditar quien esta conectado, regular el tiempo de pantalla infantil o aplicar reglas de conexion sin requerir conocimientos avanzados de telecomunicaciones.

NetGuard resuelve esta problematica implementando una arquitectura de tres capas que combina rigor academico de redes (estandares RFC 1918 y modelo TCP/IP) con una experiencia de usuario accesible y libre de tecnicismos complejos para la familia.

---

## 2. Jerarquia de Roles y Control de Acceso (RBAC)

El sistema implementa una matriz formal de control de acceso basada en roles (Role-Based Access Control) para separar las responsabilidades tecnicas de la operacion diaria del hogar:

| Rol del Usuario | Denominacion Formal | Alcance de Privilegios |
| :--- | :--- | :--- |
| **superadmin** | Superadministrador | Control total de la plataforma. Puede crear o revocar cuentas de otros administradores, configurar parametros globales de subred, gestionar categorias del sistema y realizar auditorias exhaustivas. |
| **admin** | Administrador de Red | Gestion de dispositivos, asignacion de direcciones IP y MAC, creacion de politicas de red, horarios y definicion de nuevas categorias dinamicas. No puede revocar cuentas de superadministrador. |
| **operator** | Operador del Hogar | Diseñado para padres o tutores de familia. Cuenta con una interfaz simplificada de "Control Familiar de Internet" que permite pausar o reactivar la conexion de cualquier aparato con un solo clic, sin ver terminos tecnicos. |
| **auditor** | Auditor del Sistema | Perfil de solo lectura. Permite consultar el inventario, los registros de auditoria inmutables y generar reportes tecnicos sin facultades de modificacion de datos. |

---

## 3. Modulos Principales y Componentes del Sistema

### 3.1. Ficha Tecnica Unificada con Editor Integrado
En lugar de fragmentar la visualizacion y la modificacion de un dispositivo en pantallas separadas, NetGuard agrupa en una sola interfaz modular (`/devices/<id>`):
1. **Pestaña de Ficha Tecnica**: Especificaciones completas del aparato (codigo interno, nombre, IP asignada, direccion MAC, perfil familiar, fecha de registro, politicas vigentes y trazabilidad de eventos).
2. **Pestaña de Editor Integrado**: Formulario completo de actualizacion que permite modificar parametros de red con validacion interactiva en tiempo real sin abandonar la vista del equipo.
3. **Pestaña de Control Familiar**: Panel amigable con botones directos para alternar entre "Internet Libre", "Pausa Temporal", "Modo Estudio" y "Bloqueo de Conexion".

### 3.2. Motor de Categorias Dinamicas
Permite que el Administrador y el Superadministrador extiendan el catalogo del sistema directamente desde los formularios mediante la tabla `system_categories`:
- **Tipos de Dispositivo (`device_type`)**: Permite dar de alta nuevas categorias de hardware (ej. Asistente de Voz, Consola Portatil, Camara IP Exterior).
- **Perfiles Familiares (`device_profile`)**: Permite crear roles de uso adaptados al hogar (ej. Teletrabajo, Invitados Especiales, Menores con Tutoria).
- **Destinos de Red (`policy_target`)**: Categorias de filtrado tematico (Redes Sociales, Videojuegos, Streaming, Portales Educativos).

### 3.3. Intermediario de Red y Politicas con Intermitencia
El modulo de politicas incorpora un motor de intermediacion de trafico que permite:
- **Destino Especifico**: Aplicar directivas hacia un dominio concreto (ej. `youtube.com`, `tiktok.com`, `roblox.com`) o hacia todo el trafico de Internet.
- **Modo Intermitente (Ciclos de Actividad y Pausa)**: Establece intervalos continuos de conexion (ej. 30 o 45 minutos activos) seguidos de una pausa obligatoria (ej. 15 minutos de descanso o estudio).
- **Traduccion al Adaptador de Red**: El simulador de router genera directivas formales con estructura de reglas de firewall e intermediacion por paquetes.

### 3.4. Control Familiar para Operadores (Usabilidad y Accesibilidad)
Elimina la barrera tecnica para miembros de la familia que no dominan terminos de telecomunicaciones:
- **Internet Libre (Normal)**: Acceso irrestricto sin filtros temporales.
- **Pausa Temporal de Internet**: Ideal para la hora de comer o convivir en familia sin alterar la red de los demas aparatos.
- **Modo Estudio y Tareas**: Filtra plataformas recreativas permitiendo unicamente herramientas academicas y bibliotecas virtuales.
- **Bloqueo / Corte de Conexion**: Suspende la salida a Internet del aparato seleccionado.

---

## 4. Estrategia de Validacion en Tres Capas

Para garantizar la integridad y robustez del sistema, cada dato ingresado atraviesa tres niveles independientes de comprobacion:

1. **Capa Front-End (Navegador Web)**:
   - Atributos HTML5 semanticos (`pattern`, `required`, `maxlength`).
   - JavaScript reactivo en `app.js` con analisis inmediato de direcciones IP (detecta si el usuario ingresa por error la IP del router `.1`, la direccion de red `.0` o la difusion `.255`).
   - Normalizacion en tiempo real de direcciones MAC (auto-completado de dos puntos y conversion a formato hexadecimal en mayusculas).
   - Comprobacion dinamica de coincidencia de contraseñas.

2. **Capa Back-End (Servicios y Validadores Python)**:
   - Validacion estricta contra estandares RFC 1918 mediante el modulo nativo `ipaddress`.
   - Comprobacion de pertenencia a la subred administrada (por defecto `192.168.1.0/24`).
   - Prevencion de colisiones de direccionamiento IP y duplicidad de identificadores MAC en la capa de servicio.
   - Validacion de coherencia temporal en politicas (fechas de inicio menores a fechas de termino, comprobacion de horas que cruzan la medianoche).

3. **Capa de Base de Datos (Motor MySQL 8.0+)**:
   - Restricciones DDL de unicidad `UNIQUE(ip_address, network_scope)` y `UNIQUE(mac_address)`.
   - Restricciones de verificacion `CHECK` a nivel de tabla para roles, estados administrativos y tipos de asignacion.
   - Integridad referencial con claves foraneas y eliminacion en cascada (`ON DELETE CASCADE`) para politicas y horarios vinculados.

---

## 5. Estructura del Arbol de Archivos

```text
NetGuard/
|-- app/
|   |-- models/                     Modelos relacionales con SQLAlchemy
|   |   |-- __init__.py             Exportacion centralizada de modelos y cargador de sesion
|   |   |-- audit.py                Entidad AuditLog (registro inmutable de trazabilidad)
|   |   |-- category.py             Entidad SystemCategory (tipos, perfiles y destinos dinamicos)
|   |   |-- device.py               Entidad Device (datos tecnicos e identificadores de red)
|   |   |-- policy.py               Entidad AccessPolicy (reglas, intermediario e intermitencia)
|   |   |-- router_event.py         Entidad RouterSyncLog (bitacora de directivas al router)
|   |   |-- schedule.py             Entidad AccessSchedule (ventanas horarias y dias semanales)
|   |   `-- user.py                 Entidad User (superadmin, admin, operator, auditor)
|   |-- routes/                     Controladores HTTP modulares (Flask Blueprints)
|   |   |-- __init__.py             Registro de blueprints en la factoria de aplicacion
|   |   |-- audit.py                Consulta y exportacion CSV de bitacoras de seguridad
|   |   |-- auth.py                 Inicio y cierre de sesion con proteccion CSRF
|   |   |-- categories.py           Endpoint para alta rapida de categorias dinamicas
|   |   |-- dashboard.py            Metricas globales, distribucion de perfiles y estados
|   |   |-- decorators.py           Decoradores de seguridad (@admin_required, @superadmin_required)
|   |   |-- devices.py              CRUD, Ficha Tecnica unificada y Control Familiar
|   |   |-- policies.py             Gestion de politicas de acceso e intermediario
|   |   |-- schedules.py            Programacion y evaluacion de horarios semanales
|   |   |-- settings.py             Ajustes de subred, diagnostico de base de datos y simulador
|   |   `-- users.py                Administracion de cuentas del sistema y asignacion de roles
|   |-- services/                   Capa logica de negocio y validaciones de red
|   |   |-- audit_service.py        Registro estructurado y sanitizado de eventos
|   |   |-- category_service.py     Consultas y creacion de categorias dinamicas
|   |   |-- dashboard_service.py    Calculo de metricas en tiempo real
|   |   |-- demo_seed_service.py    Carga idempotente de datos controlados de demostracion
|   |   |-- device_service.py       Reglas de negocio para alta, edicion y baja de dispositivos
|   |   |-- policy_service.py       Logica de expiracion y deteccion de contradicciones
|   |   |-- router_adapter.py       Patron Adapter: Simulador de Laboratorio y Modo Pasivo
|   |   |-- schedule_service.py     Evaluacion de cruce de medianoche y ventanas activas
|   |   |-- user_service.py         Hash seguro PBKDF2 y jerarquia de administracion de usuarios
|   |   `-- validators.py           Validadores de IP RFC 1918, MAC, hostname y coherencia
|   |-- static/                     Recursos del lado del cliente
|   |   |-- css/app.css             Estilos responsivos sin fatiga visual (temas claro y oscuro)
|   |   `-- js/app.js               Control de pestañas, validadores reactivos y modales
|   |-- templates/                  Vistas semanticas en HTML5 y Tailwind CSS
|   |   |-- base.html               Plantilla base con navegacion lateral y pie de pagina
|   |   |-- components/             Componentes reutilizables (modales, macros de iconos)
|   |   |-- devices/                Vistas de dispositivos (listado, formulario y ficha tecnica)
|   |   |-- policies/               Vistas de politicas e intermediario de conexion
|   |   |-- schedules/              Vistas de horarios semanales con selector de dias
|   |   |-- settings/               Panel de diagnostico de enlace SQL y modo de simulador
|   |   `-- users/                  Vistas de administracion de usuarios y asignacion de roles
|   |-- extensions.py               Inicializacion desacoplada de SQLAlchemy, Login y CSRF
|   `-- __init__.py                 Application Factory con cabeceras de seguridad HTTP
|-- database/                       Scripts DDL para MySQL Workbench y migraciones
|   |-- schema.sql                  Esquema relacional completo con tablas y restricciones
|   `-- schema_avance1.sql          Script relacional enfocado para evaluacion tecnica
|-- tests/                          Bateria completa de pruebas automatizadas
|   |-- conftest.py                 Fixtures de prueba con base de datos aislada en memoria
|   |-- test_audit_and_db_errors.py Pruebas de trazabilidad y tolerancia a fallos
|   |-- test_auth.py                Pruebas de sesiones, contraseñas y proteccion CSRF
|   |-- test_devices.py             Pruebas de validacion IP, MAC y prevencion de duplicados
|   |-- test_policies.py            Pruebas de politicas, vigencias y contradicciones
|   |-- test_relatoria_enhancements.py Pruebas de roles, categorias dinamicas e intermediario
|   |-- test_schedules.py           Pruebas de ventanas horarias y cruce de medianoche
|   `-- test_views_and_seed.py      Pruebas de flujo web y carga de datos de laboratorio
|-- config.py                       Configuracion por entornos (Development, Testing, Production)
|-- INICIAR_SISTEMA.bat             Script ejecutable de Windows para arranque en un clic
|-- requirements.txt                Listado de bibliotecas requeridas
`-- run.py                          Punto de entrada de ejecucion del servidor Flask
```

---

## 6. Instalacion y Puesta en Marcha

### Requisitos Previos
- Python 3.10 o superior (compatible con Python 3.14).
- Servidor de base de datos MySQL 8.0 o MariaDB 10.5 en ejecucion local.
- Navegador web moderno (Edge, Chrome, Firefox).

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/GITALETS/NetGuard.git
cd NetGuard
```

### Paso 2: Configurar el Entorno Virtual de Python
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Paso 3: Instalar Dependencias
```bash
pip install -r requirements.txt
```

### Paso 4: Inicializar la Base de Datos en MySQL
1. Abra su cliente de base de datos (por ejemplo, **MySQL Workbench**).
2. Abra y ejecute el script relacional localizado en [`database/schema.sql`](file:///C:/Users/T14%20R7/OneDrive/Escritorio/TESISAVANCE/database/schema.sql).
3. Este script creara la base de datos `red_domestica_tesis` con todas las tablas, claves foraneas e indices requeridos.

### Paso 5: Configurar Variables de Entorno
Cree un archivo `.env` en la raiz del proyecto con los siguientes parametros:
```ini
FLASK_APP=run.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=clave_secreta_de_prueba_local_2026
DATABASE_URL=mysql+pymysql://root:TU_PASSWORD@localhost:3306/red_domestica_tesis
DEFAULT_NETWORK_SCOPE=192.168.1.0/24
DEFAULT_GATEWAY_IP=192.168.1.1
```

### Paso 6: Ejecutar la Aplicacion
Puede arrancar el sistema ejecutando directamente el script por lotes [`INICIAR_SISTEMA.bat`](file:///C:/Users/T14%20R7/OneDrive/Escritorio/TESISAVANCE/INICIAR_SISTEMA.bat) con doble clic, o mediante terminal:
```bash
python run.py
```

La interfaz estara disponible inmediatamente en: **`http://127.0.0.1:5000`**

---

## 7. Verificacion de Pruebas Automatizadas

El proyecto incluye 23 pruebas automatizadas unitarias y de integracion que se ejecutan sobre una base de datos SQLite en memoria aislada, garantizando que el entorno de desarrollo y los datos reales de MySQL no sean alterados durante las pruebas:

```bash
pytest -v
```

Resultado verificado:
```text
tests/test_audit_and_db_errors.py ........ PASSED
tests/test_auth.py ....................... PASSED
tests/test_devices.py .................... PASSED
tests/test_policies.py .................. PASSED
tests/test_relatoria_enhancements.py ..... PASSED
tests/test_schedules.py ................. PASSED
tests/test_views_and_seed.py ............. PASSED

============================= 23 passed in 6.40s =============================
```
