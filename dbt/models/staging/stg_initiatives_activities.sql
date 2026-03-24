-- Staging: flatten foodSharingActivities array
-- Each row = one initiative x one activity type

{{ config(materialized='table') }}

SELECT
    i.initiative_id,
    i.initiative_name,
    i.country,
    i.city,
    i.longitude,
    i.latitude,
    a.value::VARCHAR AS activity_type
FROM {{ ref('stg_initiatives') }} i,
    LATERAL FLATTEN(input => i.food_sharing_activities_raw, outer => true) a
WHERE a.value IS NOT NULL
