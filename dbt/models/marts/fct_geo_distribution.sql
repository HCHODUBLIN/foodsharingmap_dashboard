-- Gold layer: geographic distribution of initiatives
-- Dashboard Tile 2: country and city level initiative counts

{{ config(
    materialized='table',
    cluster_by=['country']
) }}

SELECT
    country,
    city,
    COUNT(DISTINCT initiative_id) AS initiative_count,
    AVG(longitude)                AS avg_longitude,
    AVG(latitude)                 AS avg_latitude,
    ARRAY_AGG(DISTINCT activity_type) AS activity_types,
    COUNT(DISTINCT activity_type) AS activity_type_count
FROM {{ ref('int_initiatives_activities') }}
WHERE country IS NOT NULL
GROUP BY country, city
ORDER BY initiative_count DESC
