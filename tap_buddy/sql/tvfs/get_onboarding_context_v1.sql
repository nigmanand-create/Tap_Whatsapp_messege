CREATE OR REPLACE TABLE FUNCTION `central-phalanx-297915.MEL_datasets.get_onboarding_context_v1`(json_payload STRING)
AS (
  WITH params AS (
    SELECT JSON_EXTRACT_SCALAR(json_payload, '$.phone') AS contact_phone
  )
  SELECT
    COUNT(DISTINCT s.student_id) AS total_registrations,
    COUNT(DISTINCT CASE WHEN s.school_id = m.school_id THEN s.student_id END) AS school_registrations,
    MAX(m.school_name) AS school_name
  FROM `central-phalanx-297915.MEL_datasets.TLM24_EducatorMaster` m
  CROSS JOIN params p
  LEFT JOIN `central-phalanx-297915.MEL_datasets.TLM24_StudentMasterData` s
    ON m.district = s.district
  WHERE m.phone_number = p.contact_phone
  GROUP BY m.school_id
  ORDER BY school_registrations DESC, m.school_id ASC
  LIMIT 1
);
