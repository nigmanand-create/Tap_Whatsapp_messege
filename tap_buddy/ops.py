import frappe
import os


# ---------------------------------------------------------------------------
# SECURITY NOTICE
# ---------------------------------------------------------------------------
# DO NOT add any function that hardcodes tokens, refresh tokens, webhook
# secrets, phone numbers, or other credentials in this file.
# This file is Git-tracked; hardcoded secrets become permanent in history.
# Use environment variables or the Frappe UI to configure secrets.
# ---------------------------------------------------------------------------


def apply_lms_from_env():
    """Apply LMS Integration Settings from environment variables.

    Reads LMS_BASE_URL, LMS_API_KEY, and LMS_POLLING_ENABLED from the
    process environment and writes them into the LMS Integration Settings
    single doc.

    Usage:
        export LMS_BASE_URL="https://lms.example.com"
        export LMS_API_KEY="key:secret"
        bench --site <site> execute "tap_buddy.ops.apply_lms_from_env"
    """
    s = frappe.get_single("LMS Integration Settings")

    base = os.getenv("LMS_BASE_URL")
    key = os.getenv("LMS_API_KEY")
    polling = os.getenv("LMS_POLLING_ENABLED")

    if base:
        s.lms_base_url = base
    if key:
        s.lms_api_key = key
    if polling is not None:
        s.polling_enabled = 1 if polling.lower() in ("1", "true", "yes") else 0

    s.save()
    frappe.db.commit()
    print("Applied LMS settings from environment (if present)")


def run_send_test_from_env():
    """Load apps/tap_buddy/.env.local into env and run send_glific_test.send_from_env().

    This function allows invoking the send test from `bench --site <site> execute`.
    """
    import importlib.util

    # locate the env file inside the app
    try:
        env_path = frappe.get_app_path("tap_buddy", ".env.local")
    except Exception:
        env_path = None

    if not env_path or not os.path.exists(env_path):
        alt = os.path.join(os.getcwd(), "apps", "tap_buddy", ".env.local")
        if os.path.exists(alt):
            env_path = alt

    if not env_path or not os.path.exists(env_path):
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
    base_dir = os.path.dirname(__file__)  # apps/tap_buddy/tap_buddy
    script_path = os.path.normpath(os.path.join(base_dir, "..", "scripts", "send_glific_test.py"))
    if not os.path.exists(script_path):
        try:
            script_path = frappe.get_app_path("tap_buddy", "scripts", "send_glific_test.py")
        except Exception:
            script_path = None

    if not script_path or not os.path.exists(script_path):
        print(f"send_glific_test.py not found at expected paths; aborting (looked at {script_path})")
        return

    spec = importlib.util.spec_from_file_location("send_glific_test", script_path)
    if spec is None or spec.loader is None:
        print(f"Could not load module spec from {script_path}; aborting")
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    result = module.send_from_env()
    print("send_from_env result:", result)
    return result


def check_lms_settings():
    """Return LMS Integration Settings summary for diagnostics (no secrets).

    Invokable via: bench --site tapbuddy.local execute "tap_buddy.ops.check_lms_settings"
    """
    s = frappe.get_single("LMS Integration Settings")
    out = {
        "polling_enabled": bool(getattr(s, "polling_enabled", False)),
        "lms_base_url": getattr(s, "lms_base_url", None),
        "last_polled_at": getattr(s, "last_polled_at", None),
    }
    print(out)
    return out


def run_poll_from_ops(limit=20):
    """Invoke the LMS poll helper and print the result.

    Usage: bench --site tapbuddy.local execute "tap_buddy.ops.run_poll_from_ops(20)"
    """
    import tap_buddy.services.lms_ingestion as li
    res = li.poll_lms_students(limit=limit)
    print(res)
    return res
