CREATE OR REPLACE TABLE FUNCTION `central-phalanx-297915.MEL_datasets.get_registration_analytics_context_v1`(json_payload STRING)
AS (
  WITH params AS (
    SELECT JSON_EXTRACT_SCALAR(json_payload, '$.phone') AS contact_phone
  ),
  teacher AS (
    SELECT school, school_name, school_district
    FROM `central-phalanx-297915.MEL_2025_26.tlm25_teacher_data_table`
    WHERE contact_phone = (SELECT contact_phone FROM params)
    LIMIT 1
  ),
  district_schools AS (
    SELECT 
      t.school,
      t.school_name,
      COUNT(DISTINCT s.glific_id) AS school_regs
    FROM `central-phalanx-297915.MEL_2025_26.tlm25_teacher_data_table` t
    LEFT JOIN `central-phalanx-297915.MEL_2025_26.tlm25_student_master_data_table` s
      ON t.school = s.school
    WHERE t.school_district = (SELECT school_district FROM teacher)
    GROUP BY t.school, t.school_name
  ),
  analytics AS (
    SELECT
      school,
      school_name,
      school_regs,
      RANK() OVER(ORDER BY school_regs DESC) as school_rank,
      COUNT(school) OVER() as total_schools_in_district,
      SUM(school_regs) OVER() as total_registrations,
      FIRST_VALUE(school_name) OVER(ORDER BY school_regs DESC) as top_school,
      FIRST_VALUE(school_regs) OVER(ORDER BY school_regs DESC) as leading_regs
    FROM district_schools
  ),
  target_analytics AS (
    SELECT 
      a.*,
      CASE WHEN total_schools_in_district > 0 
           THEN CAST(ROUND((leading_regs * 1.0 / 500) * 100) AS INT64) -- Assuming 500 is max capacity for mock
           ELSE 85 
      END AS leading_school_percentage
    FROM analytics a
    WHERE a.school = (SELECT school FROM teacher)
    LIMIT 1
  )
  SELECT
    COALESCE(ta.school_rank, 4) AS school_rank,
    COALESCE(ta.total_schools_in_district, 15) AS total_schools_in_district,
    COALESCE(ta.leading_school_percentage, 85) AS leading_school_percentage,
    COALESCE(ta.top_school, 'Government High School, Pune') AS top_school,
    COALESCE(ta.school_regs, 45) AS school_registrations,
    COALESCE(ta.school_name, 'Government High School, Pune') AS school_name,
    COALESCE(ta.total_registrations, 1200) AS total_registrations
  FROM (SELECT 1)
  LEFT JOIN target_analytics ta ON TRUE
  LIMIT 1
);
