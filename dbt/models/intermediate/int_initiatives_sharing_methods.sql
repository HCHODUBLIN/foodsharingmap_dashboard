-- Intermediate: flatten howItIsShared array
-- Each row = one initiative x one sharing method

{{ config(materialized='table') }}

SELECT
    i.initiative_id,
    i.initiative_name,
    i.country,
    i.city,
    i.longitude,
    i.latitude,
    s.value::VARCHAR AS sharing_method_raw,
    CASE
        WHEN INITCAP(TRIM(s.value::VARCHAR)) IN ('Gifting', 'Selling', 'Collecting', 'Bartering')
            THEN INITCAP(TRIM(s.value::VARCHAR))
        ELSE NULL
    END AS sharing_method
FROM {{ ref('stg_initiatives') }} i,
    LATERAL FLATTEN(input => i.how_it_is_shared_raw, outer => true) s
WHERE s.value IS NOT NULL
  AND TRIM(s.value::VARCHAR) != ''
  AND CASE
        WHEN INITCAP(TRIM(s.value::VARCHAR)) IN ('Gifting', 'Selling', 'Collecting', 'Bartering')
            THEN TRUE
        ELSE FALSE
      END
