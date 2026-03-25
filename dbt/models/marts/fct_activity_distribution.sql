-- Gold layer: food sharing activity type distribution
-- Dashboard Tile 1: categorical breakdown of activity types

{{ config(
    materialized='table',
    cluster_by=['activity_type']
) }}

SELECT
    activity_type,
    COUNT(DISTINCT initiative_id)  AS initiative_count,
    COUNT(DISTINCT country)        AS country_count,
    COUNT(DISTINCT city)           AS city_count,
    ROUND(
        COUNT(DISTINCT initiative_id) * 100.0 /
        NULLIF((SELECT COUNT(DISTINCT initiative_id) FROM {{ ref('int_initiatives_activities') }}), 0),
        2
    ) AS pct_of_total
FROM {{ ref('int_initiatives_activities') }}
GROUP BY activity_type
ORDER BY initiative_count DESC
