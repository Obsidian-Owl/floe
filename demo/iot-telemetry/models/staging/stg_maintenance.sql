{{
    config(
        materialized='view',
        tags=['staging', 'bronze']
    )
}}

WITH source AS (
    SELECT * FROM {{ ref('raw_maintenance_log') }}
),

cleaned AS (
    SELECT
        log_id,
        equipment_id,
        maintenance_type,
        performed_at,
        technician,
        _loaded_at,
        -- Validate maintenance_type is in accepted list
        CASE
            WHEN maintenance_type IN ('preventive', 'corrective', 'predictive', 'emergency')
            THEN maintenance_type
            ELSE NULL
        END AS validated_maintenance_type
    FROM source
)

SELECT
    log_id,
    equipment_id,
    validated_maintenance_type AS maintenance_type,
    performed_at,
    technician,
    _loaded_at
FROM cleaned
WHERE validated_maintenance_type IS NOT NULL
