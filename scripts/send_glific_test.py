import os
import frappe
from tap_buddy.services.glific_client import GlificClient


def send_test_message(phone, message="Test message from TAP Buddy dev", dry_run=True):
    """Send a test message via GlificClient and print the response.

    If `dry_run` is True, the function will print the prepared payload and skip the HTTP call.
    """
    client = GlificClient()
    try:
        client.ensure_valid_token()
    except Exception:
        pass

    payload = {"phone": phone, "body": message}

    if dry_run:
        # Mask the phone number to avoid leaking test phone numbers into logs/terminals
        _masked_phone = phone[:3] + "*" * max(0, len(phone) - 6) + phone[-3:] if phone and len(phone) > 6 else "***"
        print("DRY_RUN: would send to", _masked_phone, "| message length:", len(message))
        return {"dry_run": True, "payload": payload}

    try:
        resp = client.send_message(phone, message)
        print("SEND_OK", resp)
        return resp
    except Exception as e:
        print("SEND_ERROR", str(e))
        raise


def send_from_env():
    """Read test phone/message from env and run send_test_message.

    Env vars: `GLIFIC_TEST_PHONE`, `GLIFIC_TEST_MESSAGE`, `DRY_RUN`.
    """
    phone = os.environ.get("GLIFIC_TEST_PHONE")
    message = os.environ.get("GLIFIC_TEST_MESSAGE", "Test message from TAP Buddy dev")
    dry_run = os.environ.get("DRY_RUN", "1") not in ("0", "false", "False")

    if not phone:
        print("No GLIFIC_TEST_PHONE env var set; aborting")
        return

    return send_test_message(phone, message, dry_run=dry_run)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # command-line mode
        phone = sys.argv[1]
        msg = sys.argv[2] if len(sys.argv) > 2 else None
        dry = os.environ.get("DRY_RUN", "1") not in ("0", "false", "False")
        send_test_message(phone, msg or "Test message from TAP Buddy dev", dry_run=dry)
    else:
        send_from_env()
