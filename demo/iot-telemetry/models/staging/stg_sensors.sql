{{
    config(
        materialized='view',
        tags=['staging', 'bronze']
    )
}}

WITH source AS (
    SELECT * FROM {{ ref('raw_sensors') }}
),

cleaned AS (
    SELECT
        sensor_id,
        equipment_id,
        sensor_type,
        location,
        installed_at,
        _loaded_at,
        -- Validate sensor_type is in accepted list
        CASE
            WHEN sensor_type IN ('temperature', 'pressure', 'vibration', 'humidity', 'flow_rate')
            THEN sensor_type
            ELSE NULL
        END AS validated_sensor_type
    FROM source
)

SELECT
    sensor_id,
    equipment_id,
    validated_sensor_type AS sensor_type,
    location,
    installed_at,
    _loaded_at
FROM cleaned
WHERE validated_sensor_type IS NOT NULL
