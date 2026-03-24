-- Staging: flatten howItIsShared array
-- Each row = one initiative x one sharing method

{{ config(materialized='table') }}

SELECT
    i.initiative_id,
    i.initiative_name,
    i.country,
    i.city,
    i.longitude,
    i.latitude,
    s.value::VARCHAR AS sharing_method
FROM {{ ref('stg_initiatives') }} i,
    LATERAL FLATTEN(input => i.how_it_is_shared_raw, outer => true) s
WHERE s.value IS NOT NULL
