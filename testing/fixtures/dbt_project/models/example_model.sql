-- Example model for floe testing
--
-- This is a minimal model used to verify dbt compilation and execution.
-- It produces a simple result set without external dependencies.

{{ config(materialized='view') }}

SELECT
    1 AS id,
    'example' AS name,
    CURRENT_TIMESTAMP AS created_at
