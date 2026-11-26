# NetGuard Home IP

<p align="center">
  <strong>Sistema web para administracion de dispositivos y politicas de acceso en redes domesticas mediante gestion de direcciones IP</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Framework-Flask%203.x-black?style=flat-square&logo=flask&logoColor=white" alt="Flask">
  <img src="https://img.shields.io/badge/Base%20de%20Datos-MySQL%208.0%2B-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/Pruebas-28%20Exitosas-brightgreen?style=flat-square&logo=pytest&logoColor=white" alt="Pytest">
  <img src="https://img.shields.io/badge/Licencia-Proyecto%20de%20Tesis-lightgrey?style=flat-square" alt="Licencia">
</p>

---

## 1. Descripcion General del Proyecto

NetGuard Home IP es una plataforma web orientada a la gestion de ciberseguridad defensiva, direccionamiento logico y control de acceso en redes locales residenciales o redes moviles de prueba.

En los entornos familiares modernos convergen multiples dispositivos: computadoras de trabajo, telefonos inteligentes, tabletas infantiles, televisiones inteligentes, consolas de videojuegos y equipos IoT. Los enrutadores domesticos convencionales suelen ofrecer interfaces tecnicas complejas o fragmentadas. NetGuard Home IP resuelve esta problematica mediante una arquitectura modular en tres capas que combina rigor academico en redes TCP/IP (RFC 1918) con una experiencia amigable tanto en computadora como en telefono movil.

---

## 2. Jerarquia de Roles y Control de Acceso (RBAC)

El sistema separa las facultades tecnicas de la operacion cotidiana del hogar mediante cuatro roles estrictos en `users` y en los decoradores de `app/routes/decorators.py`:

| Rol | Denominacion | Alcance de Privilegios |
| :--- | :--- | :--- |
| **superadmin** | Superadministrador | Control total del sistema. Administra usuarios (incluidos administradores), configura parametros globales y gestiona categorias dinamicas. |
| **admin** | Administrador de Red | Gestiona dispositivos, politicas de acceso, horarios semanales (individuales o globales), categorias dinamicas y monitoreo en vivo. |
| **operator** | Operador del Hogar | Enfocado en padres o tutores sin perfil tecnico. Modula el acceso familiar de los equipos (Internet Libre, Pausa Temporal, Modo Estudio, Bloqueo) desde una vista simplificada; no crea ni edita reglas o horarios tecnicos ni categorias. |
| **auditor** | Auditor | Perfil de solo lectura para consultar inventario, horarios, monitoreo y exportar bitacoras de auditoria en CSV sin capacidad de modificar datos. |

---

## 3. Explicacion Detallada de Modulos y Funcionalidades

### 3.1. Monitor de Red en Vivo y Acceso desde Telefono (`/network`)
Implementado en `app/services/network_probe_service.py` y `app/routes/network.py`, esta disenado especificamente para operar con cualquier modem domestico, mini-modem portatil con chip telefonico (MiFi) o zona Wi-Fi compartida:
- **Deteccion Automatica de Red y Subred**: Identifica en automatico la interfaz Wi-Fi activa, la direccion IP local del servidor, la puerta de enlace (modem o mini-modem) y la subred CIDR vigente (por ejemplo `192.168.8.0/24`, `192.168.0.0/24`, `192.168.1.0/24` o `192.168.96.0/20`).
- **Codigos QR Locales para Celulares**: Genera codigos QR vectoriales SVG sin depender de servicios externos para abrir inmediatamente el panel completo en el telefono del presentador o el portal de estado en vivo en otro telefono.
- **Descubrimiento en Tiempo Real (ARP + Barrido ICMP)**: Lee la cache ARP fisica del sistema operativo y realiza un sondeo ICMP paralelo para listar los equipos conectados actualmente al mini-modem con su IP, direccion MAC y latencia real en milisegundos, permitiendo registrarlos en NetGuard con un solo clic.
- **Portal Cliente en Tiempo Real (`/network/mi-acceso`)**: Pagina movil ligera que identifica la IP real del telefono conectado al mini-modem (`request.remote_addr`) y se actualiza automaticamente cada 3 segundos para mostrar en vivo si el dispositivo tiene Internet Libre, Pausa Familiar, Bloqueo, Horario Activo o en que fase del ciclo de Intermitencia se encuentra.
- **Intermediario Real de Trafico HTTP/HTTPS (Puerto `8888`)**: Implementado en `app/services/intermediary_proxy.py`, permite que cualquier telefono conectado al mini-modem o hotspot configure el Proxy Wi-Fi hacia la IP de la laptop (`:8888`) para detener y filtrar en tiempo real videos, busquedas, Modo Estudio y ciclos de intermitencia por dominio.

### 3.2. Administracion de Dispositivos y Ficha Unificada (`/devices`)
- **Entrada Segmentada IPv4 con Puntos Fijos**: Campo intuitivo dividido en cuatro octetos (`XXX . XXX . XXX . XXX`) que avanza automaticamente entre octetos y adapta la subred privada sugerida al mini-modem o Wi-Fi conectado.
- **Ficha Tecnica Unificada (`/devices/<id>`)**: Centraliza en pestanas responsivas:
  1. Especificaciones tecnicas, historial reciente, directivas del adaptador y prueba de **Ping ICMP en tiempo real**.
  2. Editor de parametros de red integrado (exclusivo para `admin` y `superadmin`).
  3. Panel amigable de **Control Familiar de Internet** (botones de un toque para operadores y administradores).
- **Menus Contextuales tipo Hamburguesa**: En tablas de escritorio, las acciones secundarias (Editar, Pausar, Quitar) se agrupan en menus desplegables compactos que evitan la dispersion horizontal de botones.

### 3.3. Politicas de Acceso e Intermediario con Intermitencia (`/policies`)
- Soporta seis tipos de politicas: Autorizacion Administrativa, Acceso Temporal, Horarios Permitidos, Restricciones de Navegacion Configurables, Politica Permanente y **Control Intermediario con Intermitencia**.
- **Intermediario de Destino e Intermitencia**: Permite orientar reglas hacia un dominio especifico (ej. `youtube.com`, `tiktok.com`, `roblox.com`) configurando ciclos continuos de minutos activos seguidos de minutos de pausa obligatoria.
- **Prevencion de Contradicciones y Vigencia Automatica**: Evita solapamientos activos con acciones opuestas en la misma prioridad y actualiza automaticamente politicas vencidas a `expired`.

### 3.4. Horarios Familiares de Uso (`/schedules`)
- Permite programar reglas semanales (con botones rapidos de Lunes a Viernes, Fin de Semana o Todos los dias) y ventanas nocturnas que cruzan la medianoche (`start_time > end_time`).
- **Horarios Globales para Toda la Casa**: Permite asignar un horario a **"Todos los dispositivos (Toda la casa - Excepto bloqueados)"** (`device_id IS NULL`) ademas de dispositivos individuales.
- **Exclusion Automatica de Equipos Bloqueados**: Los equipos cuyo estado administrativo es `blocked` quedan excluidos de los selectores de horarios porque ya tienen el acceso cortado.

### 3.5. Motor de Categorias Dinamicas (`/categories`)
Permite que `admin` y `superadmin` creen nuevas opciones desde los formularios sin editar codigo fuente, almacenandolas en la tabla `system_categories`:
- Tipos de aparato (`device_type`), perfiles familiares (`device_profile`), estados/permisos (`admin_status`) y destinos de filtrado (`policy_target`).

### 3.6. Adaptador de Router, Auditoria y Diseno Movil
- **Patron Adapter (`app/services/router_adapter.py`)**: Separa estrictamente la gestion en base de datos MySQL de la capa de comunicacion con router (`LabSimulatorRouterAdapter` y `PassiveNullRouterAdapter`), distinguiendo entre registros en BD, simulacion de laboratorio y aplicacion fisica real.
- **Bitacora Inmutable de Auditoria (`/audit`)**: Registra altas, cambios de estado, evaluaciones en vivo, escaneos de red y exportacion a CSV redactando cualquier credencial sensible.
- **Interfaz Responsiva Adaptada a Telefono**: Incluye barra inferior fija de navegacion tactil en dispositivos moviles (`< 1024px`), vista de tarjetas sin desplazamiento horizontal en lugar de tablas anchas en pantallas pequenas y controles compatibles con pantallas tactiles.

---

## 4. Guia Rapida para Demostracion en Tiempo Real con Mini-Modem y Telefono

Para presentar evidencia en tiempo real fuera de casa usando un mini-modem portatil con chip telefonico (o hotspot Wi-Fi):

1. **Conectar la PC y los telefonos**: Conecte la laptop donde corre el servidor y los telefonos de prueba a la misma red Wi-Fi emitida por el mini-modem.
2. **Permitir trafico local en Windows Firewall (una sola vez)**: Al iniciar la aplicacion en la red nueva del mini-modem, seleccione la red como Privada o ejecute en PowerShell como Administrador:
   ```powershell
   New-NetFirewallRule -DisplayName "NetGuard Home IP Puertos 5000 y 8888" -Direction Inbound -Protocol TCP -LocalPort 5000,8888 -Action Allow -Profile Private,Public
   ```
3. **Arrancar el sistema**: Ejecute `INICIAR_SISTEMA.bat` o `py run.py`. El servidor escucha en todas las interfaces (`0.0.0.0:5000`) e imprime en consola la URL exacta de red Wi-Fi (ejemplo: `http://192.168.8.100:5000`).
4. **Abrir desde tu telefono (sin estar en la PC)**: En el panel lateral entre a **Monitor en Vivo** y escanee el primer **Codigo QR** con la camara de su telefono para operar el sistema de manera tactil.
5. **Escaneo y prueba en tiempo real**:
   - Presione **Escanear Mini-Modem / Wi-Fi** para descubrir en vivo los telefonos conectados con su IP y MAC reales.
   - Si el mini-modem usa una subred distinta a `192.168.1.0/24` (por ejemplo `192.168.8.0/24`), presione **Adaptar Sistema a Subred** o registre directamente el equipo desde la tarjeta detectada.
   - En un segundo telefono, escanee el segundo QR (`/network/mi-acceso`) y observe como al pausar, bloquear o activar intermitencia desde su celular, la pantalla del segundo telefono y los registros de MySQL reflejan el cambio en vivo junto con las pruebas reales de latencia Ping ICMP.

---

## 5. Estructura del Proyecto (Para que Sirve Cada Archivo)

```text
TESISAVANCE/
|-- run.py                              Punto de entrada HTTP del servidor Flask (escucha LAN 0.0.0.0:5000)
|-- config.py                           Configuracion por entornos, carga de .env y sanitizacion de URIs
|-- INICIAR_SISTEMA.bat                 Lanzador rapido en Windows con arranque del servidor y navegador
|-- requirements.txt                    Dependencias base de Python requeridas por la plataforma
|-- database/
|   `-- schema.sql                      Script DDL definitivo para MySQL 8.0+ (crea red_domestica_tesis)
|-- app/
|   |-- __init__.py                     Application Factory, cabeceras de seguridad, manejadores HTTP y CLI
|   |-- extensions.py                   Instancias de SQLAlchemy, Flask-Login, Migrate y proteccion CSRF
|   |-- models/
|   |   |-- __init__.py                 Exportacion de modelos y cargador de usuarios de sesion
|   |   |-- user.py                     Modelo User con roles RBAC y hash seguro de contrasenas
|   |   |-- category.py                 Modelo SystemCategory para catalogos extensibles dinamicos
|   |   |-- device.py                   Modelo Device (IP, MAC, ambito CIDR, perfil y estado de acceso)
|   |   |-- policy.py                   Modelo AccessPolicy (vigencias, prioridad e intermitencia)
|   |   |-- schedule.py                 Modelo AccessSchedule (horarios semanales, medianoche y globales)
|   |   |-- router_event.py             Modelo RouterSyncLog (historial tecnico de directivas generadas)
|   |   `-- audit.py                    Modelo AuditLog (trazabilidad cronologica de seguridad)
|   |-- routes/
|   |   |-- __init__.py                 Registro centralizado de los 10 blueprints de la aplicacion
|   |   |-- decorators.py               Guardias de autorizacion (@write_permission_required, @admin_required, @superadmin_required)
|   |   |-- auth.py                     Autenticacion de usuarios y gestion de sesiones
|   |   |-- dashboard.py                Panel principal con metricas y accesos rapidos
|   |   |-- devices.py                  CRUD de dispositivos, Ficha Unificada y Control Familiar
|   |   |-- network.py                  Monitor en Vivo, escaneo ARP/ICMP, ping real y portal /mi-acceso
|   |   |-- policies.py                 Gestion de politicas de acceso e intermediario de trafico
|   |   |-- schedules.py                Administracion y evaluador de horarios individuales y globales
|   |   |-- categories.py               Endpoint AJAX/POST para creacion dinamica de categorias
|   |   |-- users.py                    Administracion de cuentas familiares y roles
|   |   |-- audit.py                    Consulta filtrada y exportacion CSV de bitacoras
|   |   `-- settings.py                 Diagnostico de MySQL, carga/limpieza demo y modo de adaptador
|   |-- services/
|   |   |-- network_probe_service.py    Deteccion de interfaz Wi-Fi/mini-modem, QR SVG, ARP, Ping ICMP y evaluacion en vivo
|   |   |-- intermediary_proxy.py       Servidor Proxy HTTP/HTTPS real en puerto 8888 para corte y filtrado en vivo
|   |   |-- device_service.py           Logica de negocio y unicidad IP/MAC por ambito de red
|   |   |-- policy_service.py           Validacion de intervalos, expiracion automatica y contradicciones
|   |   |-- schedule_service.py         Gestion de horarios globales/individuales y calculo de ventanas
|   |   |-- router_adapter.py           Patron Adapter (Simulador de Laboratorio vs Modo Pasivo)
|   |   |-- category_service.py         Inicializacion y registro de categorias dinamicas del sistema
|   |   |-- user_service.py             Creacion/edicion de usuarios con validacion jerarquica de roles
|   |   |-- audit_service.py            Registro sanitizado de eventos de auditoria y redaccion de secretos
|   |   |-- dashboard_service.py        Agregacion de estadisticas y proximas ventanas horarias
|   |   |-- demo_seed_service.py        Generador idempotente de datos demostrativos marcados con is_demo
|   |   `-- validators.py               Validadores estrictos RFC 1918 (IP, CIDR, MAC, hostnames y tiempos)
|   |-- static/
|   |   |-- css/app.css                 Temas Claro/Oscuro, componente IP segmentado, tablas y barra tactil movil
|   |   `-- js/app.js                   Validadores en vivo, menus hamburguesa, escaneo AJAX y auto-refresco movil
|   `-- templates/                      Vistas HTML5 Jinja2 responsivas (escritorio + tarjetas moviles)
`-- tests/                              Suite de 28 pruebas automatizadas con Pytest sobre BD en memoria
```

---

## 6. Instalacion, Base de Datos y Verificacion

### Base de Datos Activa Requerida
El sistema utiliza exclusivamente la base de datos **`red_domestica_tesis`** configurada en `.env`:
```ini
DATABASE_URL=mysql+pymysql://root:TU_PASSWORD@localhost:3306/red_domestica_tesis
```
Para crear o restaurar el esquema desde cero en MySQL 8.0+, ejecute [`database/schema.sql`](database/schema.sql).

### Ejecucion Local
```powershell
pip install -r requirements.txt
py run.py
```

### Pruebas Automatizadas
Todas las pruebas corren de forma aislada sobre SQLite en memoria sin alterar los registros reales de MySQL:
```powershell
py -3.14 -m pytest -v
```
Resultado verificado: **28 passed** cubriendo autenticacion, RBAC, validacion IP/MAC, politicas con intermitencia, horarios globales con exclusion de equipos bloqueados, deteccion de red, intermediario proxy real y vistas HTTP.
