-- =============================================================================
-- ESQUEMA RELACIONAL DE BASE DE DATOS (MySQL 8.0+ / MariaDB 10.5+)
-- Proyecto de Tesis:
-- "Sistema web para administración de dispositivos y políticas de acceso
--  en redes domésticas mediante gestión de direcciones IP"
-- =============================================================================

CREATE DATABASE IF NOT EXISTS red_domestica_tesis
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE red_domestica_tesis;

-- -----------------------------------------------------------------------------
-- 1. Tabla: users (Usuarios autorizados para administrar el sistema)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    email VARCHAR(120) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'admin',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT chk_users_role CHECK (role IN ('admin', 'operator', 'auditor'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_users_role_active ON users (role, is_active);

-- -----------------------------------------------------------------------------
-- 2. Tabla: devices (Dispositivos registrados en la red doméstica)
-- Distingue entre identificador interno, nombre, dirección IP (temporal o fija)
-- y dirección física MAC (cuando se conoce).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    internal_code VARCHAR(24) NOT NULL,
    name VARCHAR(100) NOT NULL,
    hostname VARCHAR(100) NULL,
    ip_address VARCHAR(45) NOT NULL,
    network_scope VARCHAR(45) NOT NULL DEFAULT '192.168.1.0/24',
    ip_assignment_type VARCHAR(32) NOT NULL DEFAULT 'dhcp_reservation',
    mac_address VARCHAR(17) NULL,
    device_type VARCHAR(32) NOT NULL DEFAULT 'other',
    owner_label VARCHAR(100) NULL,
    description TEXT NULL,
    admin_status VARCHAR(24) NOT NULL DEFAULT 'pending',
    router_sync_status VARCHAR(32) NOT NULL DEFAULT 'only_in_db',
    last_synced_at DATETIME NULL,
    is_demo TINYINT(1) NOT NULL DEFAULT 0,
    registered_by_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_devices_internal_code UNIQUE (internal_code),
    CONSTRAINT uq_device_ip_scope UNIQUE (ip_address, network_scope),
    CONSTRAINT uq_devices_mac_address UNIQUE (mac_address),
    CONSTRAINT fk_devices_registered_by FOREIGN KEY (registered_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT chk_devices_admin_status CHECK (
        admin_status IN ('authorized', 'restricted', 'blocked', 'pending')
    ),
    CONSTRAINT chk_devices_ip_assignment CHECK (
        ip_assignment_type IN ('static_manual', 'dhcp_reservation', 'dhcp_dynamic_observed')
    ),
    CONSTRAINT chk_devices_router_sync CHECK (
        router_sync_status IN ('only_in_db', 'simulated_applied', 'applied_confirmed', 'not_supported', 'sync_error')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_devices_ip_address ON devices (ip_address);
CREATE INDEX ix_devices_admin_status ON devices (admin_status);
CREATE INDEX ix_devices_device_type ON devices (device_type);

-- -----------------------------------------------------------------------------
-- 3. Tabla: access_policies (Políticas de acceso asociadas a dispositivos)
-- Separa el estado administrativo de la política (status) del estado real de
-- aplicación en el router (enforcement_status).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_policies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description TEXT NULL,
    device_id INT NOT NULL,
    policy_type VARCHAR(40) NOT NULL,
    action VARCHAR(24) NOT NULL DEFAULT 'allow',
    priority INT NOT NULL DEFAULT 50,
    status VARCHAR(24) NOT NULL DEFAULT 'active',
    valid_from DATETIME NOT NULL,
    valid_until DATETIME NULL,
    navigation_profile VARCHAR(160) NULL,
    observations TEXT NULL,
    enforcement_status VARCHAR(32) NOT NULL DEFAULT 'stored_in_db',
    last_evaluated_at DATETIME NULL,
    is_demo TINYINT(1) NOT NULL DEFAULT 0,
    created_by_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_policies_device FOREIGN KEY (device_id)
        REFERENCES devices (id) ON DELETE CASCADE,
    CONSTRAINT fk_policies_created_by FOREIGN KEY (created_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT chk_policies_type CHECK (
        policy_type IN (
            'administrative_auth',
            'temporary_access',
            'allowed_schedule',
            'navigation_restriction',
            'permanent_access'
        )
    ),
    CONSTRAINT chk_policies_action CHECK (action IN ('allow', 'restrict', 'block')),
    CONSTRAINT chk_policies_status CHECK (status IN ('active', 'paused', 'revoked', 'expired')),
    CONSTRAINT chk_policies_enforcement CHECK (
        enforcement_status IN (
            'stored_in_db',
            'simulated_in_lab',
            'applied_in_router',
            'unsupported_by_router',
            'sync_error'
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_policies_device_status ON access_policies (device_id, status);
CREATE INDEX ix_policies_type ON access_policies (policy_type);
CREATE INDEX ix_policies_validity ON access_policies (valid_from, valid_until);

-- -----------------------------------------------------------------------------
-- 4. Tabla: access_schedules (Horarios programados por dispositivo o política)
-- Soporta ventanas dentro del mismo día y ventanas que cruzan la medianoche.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_schedules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    label VARCHAR(120) NOT NULL,
    device_id INT NOT NULL,
    policy_id INT NULL,
    days_of_week VARCHAR(32) NOT NULL,
    start_time VARCHAR(5) NOT NULL,
    end_time VARCHAR(5) NOT NULL,
    window_behavior VARCHAR(24) NOT NULL DEFAULT 'allowed_window',
    crosses_midnight TINYINT(1) NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    enforcement_note VARCHAR(255) NULL,
    is_demo TINYINT(1) NOT NULL DEFAULT 0,
    created_by_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_schedules_device FOREIGN KEY (device_id)
        REFERENCES devices (id) ON DELETE CASCADE,
    CONSTRAINT fk_schedules_policy FOREIGN KEY (policy_id)
        REFERENCES access_policies (id) ON DELETE SET NULL,
    CONSTRAINT fk_schedules_created_by FOREIGN KEY (created_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT chk_schedules_behavior CHECK (
        window_behavior IN ('allowed_window', 'restricted_window')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_schedules_device_active ON access_schedules (device_id, is_active);
CREATE INDEX ix_schedules_policy ON access_schedules (policy_id);

-- -----------------------------------------------------------------------------
-- 5. Tabla: audit_logs (Historial inmutable de eventos y auditoría del sistema)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(64) NOT NULL,
    module VARCHAR(40) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    user_id INT NULL,
    username_snapshot VARCHAR(64) NULL,
    ip_origin VARCHAR(45) NULL,
    target_type VARCHAR(40) NULL,
    target_id VARCHAR(40) NULL,
    description TEXT NOT NULL,
    metadata_json TEXT NULL,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT chk_audit_severity CHECK (
        severity IN ('info', 'warning', 'error', 'security')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_audit_created_at ON audit_logs (created_at);
CREATE INDEX ix_audit_event_module ON audit_logs (module, event_type);
CREATE INDEX ix_audit_severity ON audit_logs (severity);

-- -----------------------------------------------------------------------------
-- 6. Tabla: router_sync_logs (Trazabilidad de comunicación con adaptador router)
-- Justificación técnica: Registra cada intento de traducir una política de la
-- base de datos hacia el adaptador de red (Simulador de Laboratorio o Router),
-- separando el registro administrativo de la aplicación efectiva.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS router_sync_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    adapter_name VARCHAR(64) NOT NULL,
    operation VARCHAR(64) NOT NULL,
    device_id INT NULL,
    policy_id INT NULL,
    is_simulated TINYINT(1) NOT NULL DEFAULT 1,
    result_status VARCHAR(32) NOT NULL,
    command_preview TEXT NULL,
    response_detail TEXT NULL,
    triggered_by_id INT NULL,
    CONSTRAINT fk_rsync_device FOREIGN KEY (device_id)
        REFERENCES devices (id) ON DELETE SET NULL,
    CONSTRAINT fk_rsync_policy FOREIGN KEY (policy_id)
        REFERENCES access_policies (id) ON DELETE SET NULL,
    CONSTRAINT fk_rsync_user FOREIGN KEY (triggered_by_id)
        REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_rsync_created_at ON router_sync_logs (created_at);
CREATE INDEX ix_rsync_device ON router_sync_logs (device_id);

