import os
import re
import unittest

class TestSQLDDLSyntax(unittest.TestCase):
    """
    Verifies BigQuery Table-Valued Function (TVF) DDL files against production contracts:
    - Required output column names matching flow_registry / Flow Library specification
    - Exact routine naming conventions
    - json_payload STRING parameter binding signature
    - Absence of string interpolation or SQL injection risks
    - Deterministic single-row return contract (LIMIT 1)
    - D-01: Multi-language localization ($.lang extraction, CASE v_lang block, localized columns)

    D-01 Follow-up Observations (recorded at D-01 approval, 2026-07-06):

    [OBS-1] JSON_EXTRACT_SCALAR vs JSON_VALUE
    The project intentionally uses JSON_EXTRACT_SCALAR throughout for consistency with
    existing TVF and ContextBuilder patterns. JSON_VALUE is functionally identical in
    BigQuery (returns STRING, NULL on type mismatch) and is the SQL-standard alias.
    A future migration to JSON_VALUE is PLANNED but deferred until all TVFs are fully
    deployed and integration-tested in MEL_datasets. No behaviour change is expected.

    [OBS-2] Integration Test Gap - Localized Language Outputs
    Unit tests here verify DDL structure (syntax, columns, CASE branches) only.
    Before production rollout to MEL_datasets, the following BigQuery integration test
    scenarios must be executed manually or via a CI job with GCP credentials:
      - lang=hi  -> school_metrics must return Hindi narrative string
      - lang=mr  -> school_metrics must return Marathi narrative string
      - lang omitted (null) -> COALESCE defaults to 'en'; English narrative returned
      - lang=xx (unsupported) -> ELSE branch fires; English narrative returned
    Tracked as integration test requirement; out of scope for local pytest suite.
    """

    @classmethod
    def setUpClass(cls):
        cls.app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.tvf_dir = os.path.join(cls.app_path, "sql", "tvfs")
        # Verified output column contracts per Flow Library specification.
        cls.verified_tvfs = {
            "get_onboarding_context_v1.sql": [
                "total_registrations",
                "school_registrations",
                "school_name",
            ],
            "get_engagement_context_v1.sql": [
                "registration_count",
                "access_rate",
                "submission_rate",
                "dropout_count",
                "week_number",
                "school_metrics",
            ],
            "get_feedback_context_v1.sql": [
                "access_rate",
                "submission_rate",
                "week_number",
                "school_metrics",
                "program_metrics",
            ],
        }
        # TVFs that must implement D-01 multi-language localization
        cls.localized_tvfs = [
            "get_engagement_context_v1.sql",
            "get_feedback_context_v1.sql",
        ]

    def test_tvf_directory_exists(self):
        self.assertTrue(os.path.exists(self.tvf_dir), f"Directory missing: {self.tvf_dir}")
        self.assertTrue(os.path.isdir(self.tvf_dir), f"Not a directory: {self.tvf_dir}")

    def test_verified_ddl_files_exist(self):
        for tvf_file in self.verified_tvfs:
            file_path = os.path.join(self.tvf_dir, tvf_file)
            self.assertTrue(os.path.exists(file_path), f"Missing DDL file: {tvf_file}")

    def test_exact_routine_names(self):
        for tvf_file in os.listdir(self.tvf_dir):
            if not tvf_file.endswith(".sql"):
                continue
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            routine_name = tvf_file.replace(".sql", "")
            self.assertIn("CREATE OR REPLACE TABLE FUNCTION", content, f"{tvf_file} missing CREATE TABLE FUNCTION statement")
            self.assertIn(routine_name, content, f"{tvf_file} does not define routine {routine_name}")

    def test_json_payload_string_signature(self):
        for tvf_file in os.listdir(self.tvf_dir):
            if not tvf_file.endswith(".sql"):
                continue
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("(json_payload STRING)", content, f"{tvf_file} must use exact signature (json_payload STRING)")

    def test_absence_of_string_interpolation(self):
        for tvf_file in os.listdir(self.tvf_dir):
            if not tvf_file.endswith(".sql"):
                continue
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Ensure parameters are extracted safely from json_payload without direct SQL string concatenation or formatting
            self.assertIn("JSON_EXTRACT_SCALAR(json_payload", content, f"{tvf_file} must extract arguments from json_payload via JSON_EXTRACT_SCALAR")
            self.assertNotIn("'%s'", content, f"{tvf_file} contains forbidden string interpolation placeholder '%s'")
            self.assertNotIn("{}", content, f"{tvf_file} contains forbidden string interpolation placeholder '{{}}'")
            # Check against string concatenation of variables into query strings
            self.assertFalse(re.search(r"\|\|\s*contact_phone", content), f"{tvf_file} contains forbidden string concatenation of parameters")

    def test_deterministic_return_contract(self):
        for tvf_file in os.listdir(self.tvf_dir):
            if not tvf_file.endswith(".sql"):
                continue
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("LIMIT 1", content.upper(), f"{tvf_file} must enforce LIMIT 1 for deterministic single row return guarantee")

    def test_required_output_column_names(self):
        for tvf_file, expected_columns in self.verified_tvfs.items():
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            for col in expected_columns:
                self.assertIn(f"AS {col}", content, f"{tvf_file} missing required output column alias 'AS {col}'")

            # Specifically check against plural school_names in onboarding
            if tvf_file == "get_onboarding_context_v1.sql":
                self.assertNotIn("AS school_names", content, f"{tvf_file} must use school_name instead of school_names")

    # -------------------------------------------------------------------------
    # D-01: Multi-Language Localization Tests
    # -------------------------------------------------------------------------

    def test_d01_localized_tvfs_exist(self):
        """D-01: engagement and feedback TVF DDL files must be present in the repo."""
        for tvf_file in self.localized_tvfs:
            file_path = os.path.join(self.tvf_dir, tvf_file)
            self.assertTrue(
                os.path.exists(file_path),
                f"D-01 FAIL: Localized TVF file missing: {tvf_file}",
            )

    def test_d01_lang_extraction_present(self):
        """D-01: TVFs must extract $.lang from json_payload with COALESCE default 'en'."""
        for tvf_file in self.localized_tvfs:
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn(
                "JSON_EXTRACT_SCALAR(json_payload, '$.lang')",
                content,
                f"D-01 FAIL: {tvf_file} must extract '$.lang' from json_payload",
            )
            self.assertIn(
                "COALESCE(JSON_EXTRACT_SCALAR(json_payload, '$.lang'), 'en')",
                content,
                f"D-01 FAIL: {tvf_file} must use COALESCE with default language 'en'",
            )
            self.assertIn(
                "v_lang",
                content,
                f"D-01 FAIL: {tvf_file} must declare v_lang variable for language routing",
            )

    def test_d01_localized_narrative_columns(self):
        """D-01: Localized TVFs must produce narrative strings for 'hi', 'mr', and 'en' branches."""
        for tvf_file in self.localized_tvfs:
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Must have a CASE v_lang block routing to Hindi, Marathi, and English
            self.assertIn(
                "CASE v_lang",
                content,
                f"D-01 FAIL: {tvf_file} must contain CASE v_lang routing block",
            )
            self.assertIn(
                "WHEN 'hi' THEN",
                content,
                f"D-01 FAIL: {tvf_file} must have Hindi ('hi') language branch",
            )
            self.assertIn(
                "WHEN 'mr' THEN",
                content,
                f"D-01 FAIL: {tvf_file} must have Marathi ('mr') language branch",
            )
            self.assertIn(
                "ELSE",
                content,
                f"D-01 FAIL: {tvf_file} must have ELSE default (English) language branch",
            )
            # school_metrics column must be present in both localized TVFs
            self.assertIn(
                "AS school_metrics",
                content,
                f"D-01 FAIL: {tvf_file} must output localized 'school_metrics' column",
            )

    def test_d01_safe_arithmetic_guards(self):
        """D-01: TVFs computing rates must use SAFE_DIVIDE to prevent divide-by-zero errors."""
        for tvf_file in self.localized_tvfs:
            file_path = os.path.join(self.tvf_dir, tvf_file)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn(
                "SAFE_DIVIDE(",
                content,
                f"D-01 FAIL: {tvf_file} must use SAFE_DIVIDE() for rate calculations to prevent runtime divide-by-zero errors",
            )

    def test_d01_feedback_tvf_has_program_metrics(self):
        """D-01: feedback TVF must expose 'program_metrics' state-comparison column."""
        tvf_file = "get_feedback_context_v1.sql"
        file_path = os.path.join(self.tvf_dir, tvf_file)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn(
            "AS program_metrics",
            content,
            "D-01 FAIL: get_feedback_context_v1.sql must output 'program_metrics' localized state-comparison column",
        )
