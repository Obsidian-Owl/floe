{{
    config(
        materialized='table',
        tags=['intermediate', 'silver']
    )
}}

WITH readings AS (
    SELECT * FROM {{ ref('stg_readings') }}
),

metrics AS (
    SELECT * FROM {{ ref('int_sensor_metrics') }}
),

anomaly_calculation AS (
    SELECT
        r.reading_id,
        r.sensor_id,
        r.timestamp,
        r.value,
        r.unit,
        m.avg_value,
        m.stddev_value,
        -- Calculate deviation in standard deviations
        CASE
            WHEN m.stddev_value > 0
            THEN ABS(r.value - m.avg_value) / m.stddev_value
            ELSE 0.0
        END AS deviation_factor,
        -- Flag as anomaly if outside 3-sigma
        CASE
            WHEN m.stddev_value > 0
                AND ABS(r.value - m.avg_value) > (3 * m.stddev_value)
            THEN TRUE
            ELSE FALSE
        END AS is_anomaly
    FROM readings r
    INNER JOIN metrics m ON r.sensor_id = m.sensor_id
)

SELECT
    reading_id,
    sensor_id,
    timestamp,
    value,
    unit,
    avg_value,
    stddev_value,
    deviation_factor,
    is_anomaly
FROM anomaly_calculation
