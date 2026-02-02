{{
    config(
        materialized='table',
        tags=['marts', 'gold']
    )
}}

WITH sensors AS (
    SELECT * FROM {{ ref('stg_sensors') }}
),

metrics AS (
    SELECT * FROM {{ ref('int_sensor_metrics') }}
),

anomalies AS (
    SELECT * FROM {{ ref('int_anomaly_detection') }}
),

maintenance AS (
    SELECT * FROM {{ ref('stg_maintenance') }}
),

equipment_anomalies AS (
    SELECT
        m.equipment_id,
        COUNT(*) AS total_readings,
        SUM(CASE WHEN a.is_anomaly THEN 1 ELSE 0 END) AS anomaly_count,
        CAST(SUM(CASE WHEN a.is_anomaly THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) * 100 AS anomaly_percentage
    FROM metrics m
    INNER JOIN anomalies a ON m.sensor_id = a.sensor_id
    GROUP BY m.equipment_id
),

equipment_sensors AS (
    SELECT
        equipment_id,
        COUNT(DISTINCT sensor_id) AS sensor_count
    FROM sensors
    GROUP BY equipment_id
),

last_maintenance AS (
    SELECT
        equipment_id,
        MAX(performed_at) AS last_maintenance_date
    FROM maintenance
    GROUP BY equipment_id
),

equipment_health AS (
    SELECT
        ea.equipment_id,
        es.sensor_count,
        ea.total_readings,
        ea.anomaly_count,
        ea.anomaly_percentage,
        -- Health score: 100 - anomaly_percentage
        CAST(100.0 - COALESCE(ea.anomaly_percentage, 0.0) AS DOUBLE) AS health_score,
        lm.last_maintenance_date,
        -- Days since last maintenance
        CASE
            WHEN lm.last_maintenance_date IS NOT NULL
            THEN DATE_DIFF('day', CAST(lm.last_maintenance_date AS TIMESTAMP), CURRENT_TIMESTAMP)
            ELSE NULL
        END AS days_since_maintenance
    FROM equipment_anomalies ea
    INNER JOIN equipment_sensors es ON ea.equipment_id = es.equipment_id
    LEFT JOIN last_maintenance lm ON ea.equipment_id = lm.equipment_id
)

SELECT
    equipment_id,
    sensor_count,
    total_readings,
    anomaly_count,
    ROUND(anomaly_percentage, 2) AS anomaly_percentage,
    ROUND(health_score, 2) AS health_score,
    last_maintenance_date,
    days_since_maintenance
FROM equipment_health
ORDER BY health_score ASC  -- Lowest health score first (needs attention)
