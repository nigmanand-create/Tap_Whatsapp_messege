import frappe
import base64
import json

frappe.init(site="tapbuddy.local")
frappe.connect()
settings = frappe.get_single("TAP Buddy Settings")
token = settings.get_password("glific_access_token") or settings.get_password("glific_token")

if token and "." in token:
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            payload += "=" * ((4 - len(payload) % 4) % 4)
            decoded = base64.b64decode(payload).decode("utf-8")
            print("Decoded payload:", decoded)
            # Try to parse json
            print("Parsed:", json.loads(decoded))
    except Exception as e:
        print("Error decoding:", e)
else:
    print("Token not found or invalid format:", token)
