"""
test_e01_poll_response_doctype.py

Task E-01: TAP Poll Response DocType
Verifies that:
1. The DocType JSON schema exists and is valid.
2. All 7 required fields are present with correct fieldtype.
3. response_id is marked unique and required.
4. All fields are read_only (immutable record).
5. Permissions grant System Manager full access and TAP Manager read-only.
6. Naming rule is Random (hash-based autoname).
7. Sort is by submitted_at DESC.
8. The Python controller class can be imported without errors.
"""
import json
import os
import unittest


DOCTYPE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tap_buddy",
    "doctype",
    "tap_poll_response",
)
SCHEMA_PATH = os.path.join(DOCTYPE_DIR, "tap_poll_response.json")
CONTROLLER_PATH = os.path.join(DOCTYPE_DIR, "tap_poll_response.py")
INIT_PATH = os.path.join(DOCTYPE_DIR, "__init__.py")

REQUIRED_FIELDS = {
    "response_id": "Data",
    "flow_id": "Data",
    "phone_number": "Data",
    "school_code": "Data",
    "poll_question": "Text",
    "selected_option": "Data",
    "submitted_at": "Datetime",
}


def _load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestE01DocTypeFiles(unittest.TestCase):
    """E-01: All three DocType files must exist."""

    def test_schema_json_exists(self):
        self.assertTrue(
            os.path.exists(SCHEMA_PATH),
            "E-01 FAIL: tap_poll_response.json is missing"
        )

    def test_controller_py_exists(self):
        self.assertTrue(
            os.path.exists(CONTROLLER_PATH),
            "E-01 FAIL: tap_poll_response.py is missing"
        )

    def test_init_py_exists(self):
        self.assertTrue(
            os.path.exists(INIT_PATH),
            "E-01 FAIL: __init__.py is missing from tap_poll_response package"
        )


class TestE01DocTypeSchemaFields(unittest.TestCase):
    """E-01: The JSON schema must define all 7 fields with correct types."""

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()
        cls.fields_by_name = {f["fieldname"]: f for f in cls.schema.get("fields", [])}

    def test_doctype_name(self):
        self.assertEqual(
            self.schema.get("name"),
            "TAP Poll Response",
            "E-01 FAIL: DocType name must be 'TAP Poll Response'"
        )

    def test_module_is_tap_buddy(self):
        self.assertEqual(
            self.schema.get("module"),
            "TAP Buddy",
            "E-01 FAIL: DocType must belong to 'TAP Buddy' module"
        )

    def test_all_required_fields_present(self):
        missing = set(REQUIRED_FIELDS.keys()) - set(self.fields_by_name.keys())
        self.assertEqual(
            missing, set(),
            f"E-01 FAIL: Missing required fields: {missing}"
        )

    def test_field_types_correct(self):
        for fieldname, expected_type in REQUIRED_FIELDS.items():
            actual_type = self.fields_by_name.get(fieldname, {}).get("fieldtype")
            self.assertEqual(
                actual_type,
                expected_type,
                f"E-01 FAIL: Field '{fieldname}' has type '{actual_type}', expected '{expected_type}'"
            )

    def test_response_id_is_unique(self):
        response_id = self.fields_by_name.get("response_id", {})
        self.assertTrue(
            bool(response_id.get("unique")),
            "E-01 FAIL: 'response_id' field must be marked unique=1"
        )

    def test_response_id_is_required(self):
        response_id = self.fields_by_name.get("response_id", {})
        self.assertTrue(
            bool(response_id.get("reqd")),
            "E-01 FAIL: 'response_id' field must be marked reqd=1"
        )

    def test_all_fields_are_read_only(self):
        """All fields must be read_only — poll responses are immutable."""
        for fld in self.schema.get("fields", []):
            self.assertTrue(
                bool(fld.get("read_only")),
                f"E-01 FAIL: Field '{fld['fieldname']}' must be read_only=1 (immutable record)"
            )


class TestE01DocTypeNamingAndSorting(unittest.TestCase):
    """E-01: Naming rule and sort order must match the spec."""

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()

    def test_naming_rule_is_random(self):
        self.assertEqual(
            self.schema.get("naming_rule"),
            "Random",
            "E-01 FAIL: naming_rule must be 'Random' (hash-based autoname)"
        )

    def test_autoname_is_hash(self):
        self.assertEqual(
            self.schema.get("autoname"),
            "hash",
            "E-01 FAIL: autoname must be 'hash'"
        )

    def test_sort_field_is_submitted_at(self):
        self.assertEqual(
            self.schema.get("sort_field"),
            "submitted_at",
            "E-01 FAIL: sort_field must be 'submitted_at'"
        )

    def test_sort_order_is_desc(self):
        self.assertEqual(
            self.schema.get("sort_order"),
            "DESC",
            "E-01 FAIL: sort_order must be 'DESC'"
        )

    def test_title_field_is_response_id(self):
        self.assertEqual(
            self.schema.get("title_field"),
            "response_id",
            "E-01 FAIL: title_field must be 'response_id'"
        )


class TestE01DocTypePermissions(unittest.TestCase):
    """E-01: System Manager gets full access; TAP Manager gets read-only."""

    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()
        cls.perms_by_role = {
            p["role"]: p for p in cls.schema.get("permissions", [])
        }

    def test_system_manager_has_create_permission(self):
        sm = self.perms_by_role.get("System Manager", {})
        self.assertEqual(
            sm.get("create"), 1,
            "E-01 FAIL: System Manager must have create=1"
        )

    def test_system_manager_has_read_permission(self):
        sm = self.perms_by_role.get("System Manager", {})
        self.assertEqual(
            sm.get("read"), 1,
            "E-01 FAIL: System Manager must have read=1"
        )

    def test_system_manager_has_delete_permission(self):
        sm = self.perms_by_role.get("System Manager", {})
        self.assertEqual(
            sm.get("delete"), 1,
            "E-01 FAIL: System Manager must have delete=1"
        )

    def test_system_manager_has_no_write_permission(self):
        """Records are immutable — write=0 even for System Manager."""
        sm = self.perms_by_role.get("System Manager", {})
        self.assertEqual(
            sm.get("write"), 0,
            "E-01 FAIL: System Manager must NOT have write permission (records are immutable)"
        )

    def test_tap_manager_has_read_permission(self):
        tm = self.perms_by_role.get("TAP Manager", {})
        self.assertIsNotNone(
            tm,
            "E-01 FAIL: TAP Manager role must be defined in permissions"
        )
        self.assertEqual(
            tm.get("read"), 1,
            "E-01 FAIL: TAP Manager must have read=1"
        )

    def test_tap_manager_cannot_create(self):
        tm = self.perms_by_role.get("TAP Manager", {})
        self.assertEqual(
            tm.get("create", 0), 0,
            "E-01 FAIL: TAP Manager must NOT have create permission"
        )

    def test_tap_manager_cannot_delete(self):
        tm = self.perms_by_role.get("TAP Manager", {})
        self.assertEqual(
            tm.get("delete", 0), 0,
            "E-01 FAIL: TAP Manager must NOT have delete permission"
        )

    def test_tap_manager_cannot_write(self):
        tm = self.perms_by_role.get("TAP Manager", {})
        self.assertEqual(
            tm.get("write", 0), 0,
            "E-01 FAIL: TAP Manager must NOT have write permission"
        )


class TestE01DocTypeControllerSyntax(unittest.TestCase):
    """E-01: Controller file must be valid Python with the correct class name."""

    def test_controller_file_is_valid_python(self):
        with open(CONTROLLER_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        try:
            compile(source, CONTROLLER_PATH, "exec")
        except SyntaxError as e:
            self.fail(f"E-01 FAIL: tap_poll_response.py has a syntax error: {e}")

    def test_controller_class_name_defined(self):
        with open(CONTROLLER_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        self.assertIn(
            "class TAPPollResponse",
            source,
            "E-01 FAIL: Controller must define 'class TAPPollResponse'"
        )

    def test_controller_inherits_document(self):
        with open(CONTROLLER_PATH, "r", encoding="utf-8") as f:
            source = f.read()
        self.assertIn(
            "Document",
            source,
            "E-01 FAIL: TAPPollResponse must inherit from frappe Document"
        )


if __name__ == "__main__":
    unittest.main()
