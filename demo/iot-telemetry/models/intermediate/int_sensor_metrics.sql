{{
    config(
        materialized='table',
        tags=['intermediate', 'silver']
    )
}}

WITH readings AS (
    SELECT * FROM {{ ref('stg_readings') }}
),

sensors AS (
    SELECT * FROM {{ ref('stg_sensors') }}
),

aggregated AS (
    SELECT
        r.sensor_id,
        AVG(r.value) AS avg_value,
        MIN(r.value) AS min_value,
        MAX(r.value) AS max_value,
        STDDEV(r.value) AS stddev_value,
        COUNT(*) AS reading_count
    FROM readings r
    GROUP BY r.sensor_id
)

SELECT
    a.sensor_id,
    s.equipment_id,
    s.sensor_type,
    s.location,
    s.installed_at,
    a.avg_value,
    a.min_value,
    a.max_value,
    COALESCE(a.stddev_value, 0.0) AS stddev_value,
    a.reading_count
FROM aggregated a
INNER JOIN sensors s ON a.sensor_id = s.sensor_id
