import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
APPS_FRAPPE = os.path.join(ROOT, "apps", "frappe")
if APPS_FRAPPE not in sys.path:
    sys.path.insert(0, APPS_FRAPPE)

import frappe
from frappe import init, connect, destroy
from tap_buddy.services.glific_client import GlificClient

SITE_NAME = None
SITES_PATH = None


def init_site(site_name="tapbuddy.local"):
    global SITE_NAME, SITES_PATH
    SITE_NAME = site_name
    SITES_PATH = os.path.abspath(os.path.join(ROOT, "sites"))
    init(site=site_name, sites_path=SITES_PATH)
    connect()


def ensure_site_thread():
    if not getattr(frappe.local, "site", None):
        if not SITE_NAME or not SITES_PATH:
            raise RuntimeError("Site context not initialized for thread")
        init(site=SITE_NAME, sites_path=SITES_PATH)
        connect()


def safe_print(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()


def run_get_contact(phone, label="get_contact"):
    ensure_site_thread()
    client = GlificClient()
    try:
        safe_print(f"[{label}] created GlificClient")
        contact = client.get_contact(phone)
        safe_print(f"[{label}] result=", contact)
        return True, contact
    except Exception as exc:
        safe_print(f"[{label}] exception=", repr(exc))
        return False, exc


def run_send_message(phone, message, label="send_message"):
    ensure_site_thread()
    client = GlificClient()
    try:
        safe_print(f"[{label}] created GlificClient")
        result = client.send_message(phone, message)
        safe_print(f"[{label}] result=", result)
        return True, result
    except Exception as exc:
        safe_print(f"[{label}] exception=", repr(exc))
        return False, exc


def sequential_run(phone, message, repeat):
    safe_print("=== SEQUENTIAL RUN START ===")
    for idx in range(1, repeat + 1):
        safe_print(f"--- sequential iteration {idx}/{repeat} ---")
        run_get_contact(phone, label=f"SEQ-get_contact-{idx}")
        run_send_message(phone, message, label=f"SEQ-send_message-{idx}")
        time.sleep(1)
    safe_print("=== SEQUENTIAL RUN COMPLETE ===")


def run_worker_process(task_name, phone, message, label):
    args = [
        sys.executable,
        os.path.abspath(__file__),
        "--worker",
        "--task",
        task_name,
        "--phone",
        phone,
        "--label",
        label,
        "--site",
        SITE_NAME,
    ]
    if task_name == "send_message":
        args += ["--message", message]

    safe_print(f"[{label}] spawning subprocess: {args}")
    proc = subprocess.run(args, capture_output=True, text=True)
    safe_print(f"[{label}] exit_code={proc.returncode}")
    if proc.stdout:
        safe_print(proc.stdout.strip())
    if proc.stderr:
        safe_print(proc.stderr.strip())
    return proc.returncode == 0


def concurrent_run(phone, message, repeat, workers):
    safe_print("=== CONCURRENT RUN START ===")
    tasks = []
    for idx in range(1, repeat + 1):
        tasks.append(("get_contact", phone, None, f"CONC-get_contact-{idx}"))
        tasks.append(("send_message", phone, message, f"CONC-send_message-{idx}"))

    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(run_worker_process, task_name, phone, message, label): (task_name, label)
            for task_name, phone, message, label in tasks
        }
        for future in as_completed(future_to_task):
            task_name, label = future_to_task[future]
            try:
                success = future.result()
                safe_print(f"[TASK COMPLETE] {label} task={task_name} success={success}")
                results.append(success)
            except Exception as exc:
                safe_print(f"[TASK ERROR] {label} task={task_name} exception={repr(exc)}")
                results.append(False)

    safe_print("=== CONCURRENT RUN COMPLETE ===")
    return results


def parse_args():
    parser = argparse.ArgumentParser(description="Glific client trace reproducer")
    parser.add_argument("--phone", required=True, help="Phone number to query and send to")
    parser.add_argument("--message", default="TAP Buddy diagnostic run", help="Message body for send_message")
    parser.add_argument("--repeat", type=int, default=3, help="Number of get_contact/send_message pairs per phase")
    parser.add_argument("--concurrent-workers", type=int, default=5, help="Number of parallel workers for concurrent phase")
    parser.add_argument("--site", default="tapbuddy.local", help="Frappe site name")
    parser.add_argument("--worker", action="store_true", help="Run a single worker task")
    parser.add_argument("--task", choices=["get_contact", "send_message"], help="Worker task name")
    parser.add_argument("--label", default="worker", help="Worker label for logging")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    init_site(args.site)
    try:
        if args.worker:
            if args.task == "get_contact":
                success, payload = run_get_contact(args.phone, label=args.label)
                sys.exit(0 if success else 1)
            if args.task == "send_message":
                success, payload = run_send_message(args.phone, args.message, label=args.label)
                sys.exit(0 if success else 1)
            sys.exit(1)

        sequential_run(args.phone, args.message, args.repeat)
        concurrent_run(args.phone, args.message, args.repeat, args.concurrent_workers)
    finally:
        destroy()
