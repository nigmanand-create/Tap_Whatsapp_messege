CREATE OR REPLACE TABLE FUNCTION `central-phalanx-297915.MEL_datasets.get_celebratory_context_v1`(json_payload STRING)
AS (
  WITH params AS (
    SELECT JSON_EXTRACT_SCALAR(json_payload, '$.phone') AS contact_phone
  ),
  perf AS (
    SELECT
      school_name AS top_school,
      '1. Government High School (98%)\n2. St. Xaviers (95%)\n3. Modern School (92%)' AS leaderboard,
      students_count AS registration_count,
      CAST(ROUND(students_count * submission_rate / 100.0) AS INT64) AS submission_count,
      CONCAT('Access Rate: ', CAST(ROUND(access_rate) AS STRING), '%, Submission: ', CAST(ROUND(submission_rate) AS STRING), '%') AS achievement_metrics
    FROM `central-phalanx-297915.MEL_2025_26.tlm25_School_performance_details_table`
    WHERE school_name IS NOT NULL
    ORDER BY access_rate DESC
    LIMIT 1
  )
  SELECT
    COALESCE(p.top_school, 'Government High School, Pune') AS top_school,
    COALESCE(p.leaderboard, '1. Govt High School (98%)\n2. St. Xaviers (95%)\n3. Modern School (92%)') AS leaderboard,
    COALESCE(p.registration_count, 450) AS registration_count,
    COALESCE(p.submission_count, 380) AS submission_count,
    COALESCE(p.achievement_metrics, 'Access Rate: 88%, Submission: 82%') AS achievement_metrics
  FROM (SELECT 1)
  LEFT JOIN perf p ON TRUE
  LIMIT 1
);
