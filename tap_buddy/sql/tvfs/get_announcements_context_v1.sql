-- get_announcements_context_v1
-- NOTE: tlm25_Activity_video_details is a Google Sheets external table requiring Drive API access.
-- The SA tap-buddy-bigquery@central-phalanx-297915.iam.gserviceaccount.com does not have
-- Drive credentials. This TVF serves hardcoded QA defaults. To enable live data:
-- 1. Share the Google Sheet with tap-buddy-bigquery@central-phalanx-297915.iam.gserviceaccount.com
-- 2. Update this TVF to query tlm25_Activity_video_details directly.
CREATE OR REPLACE TABLE FUNCTION `central-phalanx-297915.MEL_datasets.get_announcements_context_v1`(json_payload STRING)
AS (
  SELECT
    12 AS week_number,
    '{"Grade 9": "https://youtu.be/sample9", "Grade 10": "https://youtu.be/sample10"}' AS grade_wise_youtube_links
  LIMIT 1
);
