-- Staging: cleaned and typed initiative data
-- Extracts fields from raw JSON and casts to appropriate types
-- Filters to latest ingestion snapshot only

{{ config(materialized='view') }}

SELECT
    raw_json:id::VARCHAR                    AS initiative_id,
    raw_json:name::VARCHAR                  AS initiative_name,
    raw_json:url::VARCHAR                   AS website_url,
    raw_json:facebookUrl::VARCHAR           AS facebook_url,
    raw_json:xUrl::VARCHAR                  AS x_url,
    raw_json:instagramUrl::VARCHAR          AS instagram_url,
    raw_json:country::VARCHAR               AS country,
    raw_json:city::VARCHAR                  AS city,
    TRY_CAST(raw_json:lng::VARCHAR AS FLOAT)  AS longitude,
    TRY_CAST(raw_json:lat::VARCHAR AS FLOAT)  AS latitude,
    raw_json:foodSharingActivities          AS food_sharing_activities_raw,
    raw_json:howItIsShared                  AS how_it_is_shared_raw,
    ingested_at,
    source_api
FROM {{ source('bronze', 'raw_initiatives') }}
WHERE raw_json:id IS NOT NULL
  AND ingested_at = (
      SELECT MAX(ingested_at) FROM {{ source('bronze', 'raw_initiatives') }}
  )
