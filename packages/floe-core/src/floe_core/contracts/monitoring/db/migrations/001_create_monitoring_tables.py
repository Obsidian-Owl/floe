"""Initial monitoring tables migration.

Tasks: T058 (Epic 3D)
Requirements: FR-031, FR-032

Creates:
- contract_check_results
- contract_violations
- contract_sla_status
- contract_daily_aggregates
- registered_contracts
- alert_dedup_state
"""

from __future__ import annotations

# Migration metadata
REVISION = "001"
DESCRIPTION = "Create contract monitoring tables"

# SQL for manual migration (also created by Base.metadata.create_all())
UP_SQL = """
CREATE TABLE IF NOT EXISTS contract_check_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    duration_seconds DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_check_results_contract_time
    ON contract_check_results (contract_name, timestamp);
CREATE INDEX IF NOT EXISTS ix_check_results_type_time
    ON contract_check_results (check_type, timestamp);

CREATE TABLE IF NOT EXISTS contract_violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL,
    contract_version VARCHAR(50) NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    element VARCHAR(255),
    expected_value TEXT,
    actual_value TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    affected_consumers JSONB NOT NULL DEFAULT '[]'::jsonb,
    check_duration_seconds DOUBLE PRECISION NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_violations_contract_time
    ON contract_violations (contract_name, timestamp);
CREATE INDEX IF NOT EXISTS ix_violations_severity_time
    ON contract_violations (severity, timestamp);
CREATE INDEX IF NOT EXISTS ix_violations_type_contract
    ON contract_violations (violation_type, contract_name);

CREATE TABLE IF NOT EXISTS contract_sla_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL UNIQUE,
    check_type VARCHAR(50) NOT NULL,
    current_status VARCHAR(20) NOT NULL,
    compliance_pct DOUBLE PRECISION NOT NULL,
    last_violation_at TIMESTAMP WITH TIME ZONE,
    consecutive_violations INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS contract_daily_aggregates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL,
    check_type VARCHAR(50) NOT NULL,
    date TIMESTAMP WITH TIME ZONE NOT NULL,
    total_checks INTEGER NOT NULL DEFAULT 0,
    passed_checks INTEGER NOT NULL DEFAULT 0,
    failed_checks INTEGER NOT NULL DEFAULT 0,
    error_checks INTEGER NOT NULL DEFAULT 0,
    avg_duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    violation_count INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_daily_agg_contract_date
    ON contract_daily_aggregates (contract_name, date);
CREATE INDEX IF NOT EXISTS ix_daily_agg_type_date
    ON contract_daily_aggregates (check_type, date);

CREATE TABLE IF NOT EXISTS registered_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL UNIQUE,
    contract_version VARCHAR(50) NOT NULL,
    contract_data JSONB NOT NULL,
    connection_config JSONB NOT NULL,
    monitoring_overrides JSONB,
    registered_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_check_times JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS alert_dedup_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_name VARCHAR(255) NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    last_alerted_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_dedup_contract_type
    ON alert_dedup_state (contract_name, violation_type);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS alert_dedup_state;
DROP TABLE IF EXISTS registered_contracts;
DROP TABLE IF EXISTS contract_daily_aggregates;
DROP TABLE IF EXISTS contract_sla_status;
DROP TABLE IF EXISTS contract_violations;
DROP TABLE IF EXISTS contract_check_results;
"""
