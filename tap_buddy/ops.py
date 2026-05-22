import frappe


def apply_literal_values():
    """Apply Glific settings provided by the user into TAP Buddy Settings.

    WARNING: This writes secrets into the site's single Doc. Use only when
    the user has explicitly provided and consented to store these values.
    """
    s = frappe.get_single("TAP Buddy Settings")
    s.glific_url = "https://api.tap.glific.com"
    s.glific_token = "SFMyNTY.ZjdlMDJhNTYtYTFkMC00MTE1LWI2N2QtOTQyY2FkNjI0ZGMy.RpvepEvju7EM6Z8iFEUn8CZLXCgAAOypmef8JDCYcuU"
    s.glific_access_token = "SFMyNTY.ZjdlMDJhNTYtYTFkMC00MTE1LWI2N2QtOTQyY2FkNjI0ZGMy.RpvepEvju7EM6Z8iFEUn8CZLXCgAAOypmef8JDCYcuU"
    s.glific_refresh_token = "SFMyNTY.MjljZDQ3ZDMtZTNlMC00MzZkLWExZTAtNGYwNDdmMDIzMDQx.Tcb9e49Ts2w6z0p76g1sI_rpti04DsbipVBa8XypLYM"
    s.glific_token_expiry = "2026-05-19T06:11:46.304907+00:00"
    s.glific_phone_number = "919068076307"
    s.webhook_secret = "Gf456@456"
    s.save()
    frappe.db.commit()
    print("Applied Glific settings to TAP Buddy Settings")


def run_send_test_from_env():
    """Load apps/tap_buddy/.env.local into env and run send_glific_test.send_from_env().

    This function allows invoking the send test from `bench --site <site> execute`.
    """
    import os
    import importlib.util
    # locate the env file inside the app
    try:
        env_path = frappe.get_app_path("tap_buddy", ".env.local")
    except Exception:
        env_path = None

    # fallback to repository path apps/tap_buddy/.env.local
    import os
    if not env_path or not os.path.exists(env_path):
        alt = os.path.join(os.getcwd(), "apps", "tap_buddy", ".env.local")
        if os.path.exists(alt):
            env_path = alt

    if not env_path or not os.path.exists(env_path):
        # final fallback: workspace-relative path
        alt2 = "/Users/blackstar/dev/client/tap-bench/apps/tap_buddy/.env.local"
        if os.path.exists(alt2):
            env_path = alt2

    if not env_path or not os.path.exists(env_path):
        print(f".env.local not found at {env_path}; aborting")
        return

    # load env lines into os.environ
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

    # load the send_glific_test script by path and call send_from_env
    # compute path relative to this ops.py file so it works inside bench execute
    base_dir = os.path.dirname(__file__)  # apps/tap_buddy/tap_buddy
    script_path = os.path.normpath(os.path.join(base_dir, "..", "scripts", "send_glific_test.py"))
    if not os.path.exists(script_path):
        # fallback to app package path (unlikely)
        try:
            script_path = frappe.get_app_path("tap_buddy", "scripts", "send_glific_test.py")
        except Exception:
            script_path = None

    if not script_path or not os.path.exists(script_path):
        print(f"send_glific_test.py not found at expected paths; aborting (looked at {script_path})")
        return
    spec = importlib.util.spec_from_file_location("send_glific_test", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.send_from_env()
    print("send_from_env result:", result)
    return result


def check_lms_settings():
    """Return LMS Integration Settings summary for diagnostics.

    Invokable via: bench --site tapbuddy.local execute "tap_buddy.ops.check_lms_settings"
    """
    import frappe
    s = frappe.get_single("LMS Integration Settings")
    out = {
        "polling_enabled": bool(getattr(s, "polling_enabled", False)),
        "lms_base_url": getattr(s, "lms_base_url", None),
        "last_polled_at": getattr(s, "last_polled_at", None),
    }
    print(out)
    return out


def apply_literal_lms():
    """Apply literal LMS Integration Settings provided by the user.

    WARNING: writes secrets into site single Doc. Intended for one-off use.
    """
    import frappe
    import os

    s = frappe.get_single("LMS Integration Settings")

    # Read from environment so credentials live in a single env file.
    base = os.getenv("LMS_BASE_URL")
    key = os.getenv("LMS_API_KEY")
    polling = os.getenv("LMS_POLLING_ENABLED")

    if base:
        s.lms_base_url = base
    if key:
        s.lms_api_key = key
    if polling is not None:
        s.polling_enabled = 1 if str(polling).lower() in ("1", "true", "yes") else 0

    s.save()
    frappe.db.commit()
    print("Applied LMS settings from environment (if present)")


def run_poll_from_ops(limit=20):
    """Invoke the LMS poll helper and print the result.

    Usage: bench --site tapbuddy.local execute "tap_buddy.ops.run_poll_from_ops(20)"
    """
    import tap_buddy.services.lms_ingestion as li
    res = li.poll_lms_students(limit=limit)
    print(res)
    return res
