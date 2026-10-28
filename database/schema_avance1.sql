-- =============================================================================
-- ESQUEMA RELACIONAL DE BASE DE DATOS - MYSQL 8.0+ / MYSQL WORKBENCH
-- ENTREGABLE: PRIMER AVANCE DE TESIS (35% DEL SISTEMA)
-- Proyecto de Tesis:
-- "Sistema web para administración de dispositivos y políticas de acceso
--  en redes domésticas mediante gestión de direcciones IP"
-- =============================================================================

CREATE DATABASE IF NOT EXISTS red_domestica_tesis
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE red_domestica_tesis;

-- -----------------------------------------------------------------------------
-- TABLA 1: users (Control de Usuarios y Autenticación del Sistema)
-- Implementa: Hash seguro de contraseñas, roles RBAC y control de sesiones.
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
-- TABLA 2: devices (Administración Centralizada de Dispositivos e IPs)
-- Distingue claramente entre:
-- 1. Identificador interno de sistema (DEV-XXXXXX).
-- 2. Nombre amigable para el hogar.
-- 3. Dirección IP (validación RFC 1918).
-- 4. Subred de la red doméstica (CIDR).
-- 5. Dirección física MAC (cuando se conoce).
-- 6. Tipo de asignación de IP (DHCP reservado / Estática).
-- 7. Estado administrativo (authorized, restricted, blocked, pending).
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
    profile VARCHAR(32) NOT NULL DEFAULT 'family',
    owner_label VARCHAR(100) NULL,
    admin_status VARCHAR(32) NOT NULL DEFAULT 'authorized',
    description TEXT NULL,
    is_demo TINYINT(1) NOT NULL DEFAULT 0,
    router_sync_status VARCHAR(32) NOT NULL DEFAULT 'in_sync',
    last_synced_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_devices_internal_code UNIQUE (internal_code),
    CONSTRAINT uq_devices_ip_scope UNIQUE (network_scope, ip_address),
    CONSTRAINT chk_devices_admin_status CHECK (admin_status IN ('authorized', 'restricted', 'blocked', 'pending')),
    CONSTRAINT chk_devices_assignment CHECK (ip_assignment_type IN ('dhcp_reservation', 'static', 'dynamic')),
    CONSTRAINT chk_devices_sync_status CHECK (router_sync_status IN ('in_sync', 'pending_sync', 'error', 'unsupported'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_devices_scope_ip ON devices (network_scope, ip_address);
CREATE INDEX ix_devices_admin_status ON devices (admin_status);
CREATE INDEX ix_devices_type ON devices (device_type);

-- -----------------------------------------------------------------------------
-- TABLA 3: audit_logs (Historial y Auditoría de Seguridad Inmutable)
-- Registra eventos de autenticación, altas, bajas y modificaciones.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    username_snapshot VARCHAR(64) NULL,
    module VARCHAR(40) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    description VARCHAR(255) NOT NULL,
    metadata_json TEXT NULL,
    ip_source VARCHAR(45) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT chk_audit_severity CHECK (severity IN ('info', 'warning', 'error', 'critical'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX ix_audit_created_at ON audit_logs (created_at DESC);
CREATE INDEX ix_audit_module ON audit_logs (module);

-- =============================================================================
-- NOTA METODOLÓGICA DE AVANCE 1 (35%):
-- Las tablas `policies`, `schedules` y `router_sync_logs` corresponden a la
-- FASE 2 y FASE 3 del cronograma de tesis, contenidas en `schema_completo.sql`.
-- =============================================================================

