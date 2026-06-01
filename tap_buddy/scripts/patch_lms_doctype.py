import json
import os

doctype_path = "/Users/blackstar/dev/client/tap-bench/apps/tap_buddy/tap_buddy/tap_buddy/doctype/lms_integration_settings/lms_integration_settings.json"

with open(doctype_path, "r") as f:
    data = json.load(f)

# Update field_order
field_order = data["field_order"]
if "lms_username" not in field_order:
    idx = field_order.index("lms_base_url") + 1
    field_order.insert(idx, "lms_username")
    field_order.insert(idx + 1, "lms_password")

# Update fields
existing_fields = [f["fieldname"] for f in data["fields"]]
if "lms_username" not in existing_fields:
    idx = next(i for i, f in enumerate(data["fields"]) if f["fieldname"] == "lms_base_url") + 1
    data["fields"].insert(idx, {
        "fieldname": "lms_username",
        "fieldtype": "Data",
        "label": "LMS Username"
    })
    data["fields"].insert(idx + 1, {
        "fieldname": "lms_password",
        "fieldtype": "Password",
        "label": "LMS Password"
    })

data["modified"] = "2026-06-01 12:00:00.000000"

with open(doctype_path, "w") as f:
    json.dump(data, f, indent=1)

print("Updated lms_integration_settings.json")
