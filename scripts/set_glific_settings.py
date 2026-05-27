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


# ---------------------------------------------------------------------------
# SECURITY NOTICE
# ---------------------------------------------------------------------------
# DO NOT add an `apply_literal_values()` function or any function that
# hardcodes tokens, refresh tokens, webhook secrets, phone numbers, or any
# other credentials in this file.
#
# This file is Git-tracked. Hardcoded secrets will be permanently embedded
# in the repository history and will require a full git-filter-repo scrub
# to remove.
#
# To bootstrap settings on a new site, use one of these patterns:
#
#   1. Environment variables (preferred):
#        export GLIFIC_TOKEN="<value>"
#        bench --site <site> execute "tap_buddy.scripts.set_glific_settings.set_from_env"
#
#   2. Manual entry via the Frappe UI:
#        Desk > TAP Buddy Settings > (fill in the Password fields)
# ---------------------------------------------------------------------------
