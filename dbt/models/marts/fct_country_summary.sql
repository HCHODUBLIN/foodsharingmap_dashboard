-- Gold layer: country-level summary for map visualization

{{ config(
    materialized='table',
    cluster_by=['country']
) }}

SELECT
    country,
    COUNT(DISTINCT initiative_id) AS total_initiatives,
    COUNT(DISTINCT city)          AS city_count,
    ARRAY_AGG(DISTINCT activity_type) AS activity_types,
    AVG(longitude)                AS centroid_lng,
    AVG(latitude)                 AS centroid_lat
FROM {{ ref('stg_initiatives_activities') }}
WHERE country IS NOT NULL
GROUP BY country
ORDER BY total_initiatives DESC
