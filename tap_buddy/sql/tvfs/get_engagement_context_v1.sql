CREATE OR REPLACE TABLE FUNCTION `central-phalanx-297915.MEL_datasets.get_engagement_context_v1`(json_payload STRING)
AS (
  WITH params AS (
    SELECT
      JSON_EXTRACT_SCALAR(json_payload, '$.phone')  AS contact_phone,
      COALESCE(JSON_EXTRACT_SCALAR(json_payload, '$.lang'), 'en') AS v_lang
  ),
  educator AS (
    SELECT
      m.school_id,
      m.school_name,
      p.v_lang
    FROM `central-phalanx-297915.MEL_datasets.TLM24_EducatorMaster` m
    CROSS JOIN params p
    WHERE m.phone_number = p.contact_phone
    LIMIT 1
  ),
  stats AS (
    SELECT
      e.school_id,
      e.school_name,
      e.v_lang,
      COUNT(DISTINCT s.student_id)                              AS registration_count,
      SAFE_DIVIDE(
        COUNTIF(s.portal_accessed_this_week),
        NULLIF(COUNT(DISTINCT s.student_id), 0)
      ) * 100.0                                                 AS access_rate,
      SAFE_DIVIDE(
        COUNTIF(s.assignment_submitted_this_week),
        NULLIF(COUNT(DISTINCT s.student_id), 0)
      ) * 100.0                                                 AS submission_rate,
      COUNTIF(NOT s.portal_accessed_this_week)                  AS dropout_count,
      MAX(s.tracking_week)                                      AS week_number
    FROM educator e
    LEFT JOIN `central-phalanx-297915.MEL_datasets.TLM24_StudentMasterData` s
      ON s.school_id = e.school_id
    GROUP BY e.school_id, e.school_name, e.v_lang
  )
  SELECT
    IFNULL(registration_count, 0)          AS registration_count,
    IFNULL(ROUND(access_rate, 1), 0.0)     AS access_rate,
    IFNULL(ROUND(submission_rate, 1), 0.0) AS submission_rate,
    IFNULL(dropout_count, 0)               AS dropout_count,
    IFNULL(week_number, 0)                 AS week_number,
    CASE v_lang
      WHEN 'hi' THEN
        CASE
          WHEN IFNULL(ROUND(access_rate, 1), 0.0) >= 80.0 THEN 'उत्कृष्ट स्कूल'
          WHEN IFNULL(ROUND(access_rate, 1), 0.0) >= 60.0 THEN 'अच्छा प्रदर्शन'
          ELSE 'सुधार की आवश्यकता'
        END
      WHEN 'mr' THEN
        CASE
          WHEN IFNULL(ROUND(access_rate, 1), 0.0) >= 80.0 THEN 'उत्कृष्ट शाळा'
          WHEN IFNULL(ROUND(access_rate, 1), 0.0) >= 60.0 THEN 'चांगली कामगिरी'
          ELSE 'सुधारणा आवश्यक'
        END
      ELSE
        CASE
          WHEN IFNULL(ROUND(access_rate, 1), 0.0) >= 80.0 THEN 'Excelling School'
          WHEN IFNULL(ROUND(access_rate, 1), 0.0) >= 60.0 THEN 'Good Progress'
          ELSE 'Needs Improvement'
        END
    END AS school_metrics
  FROM stats
  LIMIT 1
);
