import os
import frappe


def set_from_env():
    """Set TAP Buddy Settings fields from environment variables.

    Expected env vars (all optional):
      GLIFIC_URL, GLIFIC_TOKEN, GLIFIC_ACCESS_TOKEN, GLIFIC_REFRESH_TOKEN,
      GLIFIC_TOKEN_EXPIRY (ISO datetime), GLIFIC_PHONE_NUMBER, WEBHOOK_SECRET
    """
    frappe.init_site()
    site = frappe.utils.get_site_name(frappe.local.request_host or None)
    # Use current site context
    frappe.connect()
    try:
        s = frappe.get_single("TAP Buddy Settings")
        changed = False
        mappings = {
            "GLIFIC_URL": ("glific_url", str),
            "GLIFIC_TOKEN": ("glific_token", str),
            "GLIFIC_ACCESS_TOKEN": ("glific_access_token", str),
            "GLIFIC_REFRESH_TOKEN": ("glific_refresh_token", str),
            "GLIFIC_TOKEN_EXPIRY": ("glific_token_expiry", str),
            "GLIFIC_PHONE_NUMBER": ("glific_phone_number", str),
            "WEBHOOK_SECRET": ("webhook_secret", str),
        }

        for env, (field, _type) in mappings.items():
            if os.environ.get(env):
                val = os.environ.get(env)
                setattr(s, field, val)
                changed = True

        if changed:
            s.save()
            frappe.db.commit()
            print("TAP Buddy Settings updated from environment variables")
        else:
            print("No GLIFIC_* or WEBHOOK_SECRET env vars found; nothing changed")
    finally:
        frappe.destroy()


if __name__ == "__main__":
    set_from_env()


def apply_literal_values():
    """One-off helper: apply the literal Glific settings provided by the user.

    This function is intended to be invoked via `bench --site <site> execute
    "tap_buddy.scripts.set_glific_settings.apply_literal_values"` and will
    write the values directly into the `TAP Buddy Settings` single doc.
    """
    import frappe
    s = frappe.get_single("TAP Buddy Settings")
    # Values supplied by user (do not commit these values to source control)
    s.glific_url = "https://api.tap.glific.com"
    s.glific_token = "SFMyNTY.ZjdlMDJhNTYtYTFkMC00MTE1LWI2N2QtOTQyY2FkNjI0ZGMy.RpvepEvju7EM6Z8iFEUn8CZLXCgAAOypmef8JDCYcuU"
    s.glific_access_token = "SFMyNTY.ZjdlMDJhNTYtYTFkMC00MTE1LWI2N2QtOTQyY2FkNjI0ZGMy.RpvepEvju7EM6Z8iFEUn8CZLXCgAAOypmef8JDCYcuU"
    s.glific_refresh_token = "SFMyNTY.MjljZDQ3ZDMtZTNlMC00MzZkLWExZTAtNGYwNDdmMDIzMDQx.Tcb9e49Ts2w6z0p76g1sI_rpti04DsbipVBa8XypLYM"
    s.glific_token_expiry = "2026-05-19T06:11:46.304907+00:00"
    s.glific_phone_number = "919068076307"
    s.webhook_secret = "Gf456@456"
    s.save()
    frappe.db.commit()
    print("Applied literal Glific settings to TAP Buddy Settings")
