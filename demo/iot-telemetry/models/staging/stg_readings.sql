{{
    config(
        materialized='view',
        tags=['staging', 'bronze']
    )
}}

WITH source AS (
    SELECT * FROM {{ ref('raw_readings') }}
),

cleaned AS (
    SELECT
        reading_id,
        sensor_id,
        timestamp,
        CAST(value AS DOUBLE) AS value,
        unit,
        _loaded_at
    FROM source
),

filtered AS (
    SELECT
        reading_id,
        sensor_id,
        timestamp,
        value,
        unit,
        _loaded_at
    FROM cleaned
    WHERE value BETWEEN -1000 AND 10000  -- Filter outliers
        AND value IS NOT NULL
)

SELECT * FROM filtered
