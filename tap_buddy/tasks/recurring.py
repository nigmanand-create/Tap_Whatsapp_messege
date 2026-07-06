# -*- coding: utf-8 -*-
"""
Production-Ready Recurring Campaign Template Scheduler & Execution Engine
=========================================================================
Implements distributed locking, idempotency, timezone-aware recurrence calculations,
missed execution catch-up policies, and execution previews.
"""

import frappe
from frappe.utils import get_datetime, now_datetime
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pytz

GLOBAL_LOCK_KEY = "tap_buddy:recurring_scheduler_lock"
GLOBAL_LOCK_TTL = 120  # seconds
TEMPLATE_LOCK_TTL = 60  # seconds

def compute_idempotency_key(template_name: str, scheduled_dt: datetime) -> str:
    """
    Computes a deterministic, unique idempotency key for a recurrence window.
    Format: RCT:<template_name>:<YYYYMMDDHHMM>
    """
    formatted_time = scheduled_dt.strftime("%Y%m%d%H%M")
    return f"RCT:{template_name}:{formatted_time}"

def is_window_executed(idempotency_key: str) -> bool:
    """Checks whether an execution record already exists for the given idempotency key."""
    return bool(frappe.db.exists("Generated Campaign History", {"idempotency_key": idempotency_key}))

def calculate_next_execution(
    recurrence_type: str,
    from_dt: datetime,
    execution_timezone: str = "Asia/Kolkata",
    cron_expression: Optional[str] = None
) -> datetime:
    """
    Calculates the next execution timestamp relative to the target timezone.
    Returns UTC-equivalent naive datetime ready for storage.
    """
    try:
        from croniter import croniter
    except ImportError:
        frappe.throw("croniter package is required for timezone-aware recurrence calculations.")

    tz = pytz.timezone(execution_timezone or "Asia/Kolkata")
    
    # Ensure from_dt is treated as UTC if naive
    if from_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(from_dt)
    else:
        utc_dt = from_dt.astimezone(pytz.utc)

    local_dt = utc_dt.astimezone(tz)

    if recurrence_type == "Daily":
        cron_expr = f"{local_dt.minute} {local_dt.hour} * * *"
    elif recurrence_type == "Weekly":
        cron_dow = (local_dt.weekday() + 1) % 7
        cron_expr = f"{local_dt.minute} {local_dt.hour} * * {cron_dow}"
    elif recurrence_type == "Monthly":
        cron_expr = f"{local_dt.minute} {local_dt.hour} {local_dt.day} * *"
    elif recurrence_type == "Custom Cron":
        if not cron_expression:
            frappe.throw("cron_expression is required for Custom Cron recurrence.")
        cron_expr = cron_expression
    else:
        frappe.throw(f"Unsupported recurrence_type: {recurrence_type}")

    iter_obj = croniter(cron_expr, local_dt)
    next_local = iter_obj.get_next(datetime)
    
    # Convert back to UTC naive datetime
    next_utc = next_local.astimezone(pytz.utc).replace(tzinfo=None)
    return next_utc

def preview_next_executions(
    template_doc: Any,
    count: int = 20,
    from_dt: Optional[datetime] = None
) -> List[str]:
    """
    Returns a list of upcoming scheduled execution datetimes (ISO format)
    without creating any campaigns or modifying state.
    """
    results = []
    current_dt = from_dt or get_datetime(template_doc.next_execution_date or template_doc.start_date or now_datetime())
    
    recurrence_type = template_doc.recurrence_type
    tz_str = getattr(template_doc, "execution_timezone", "Asia/Kolkata")
    cron_expr = getattr(template_doc, "cron_expression", None)
    end_date = get_datetime(template_doc.end_date) if getattr(template_doc, "end_date", None) else None

    for _ in range(count):
        next_dt = calculate_next_execution(
            recurrence_type=recurrence_type,
            from_dt=current_dt,
            execution_timezone=tz_str,
            cron_expression=cron_expr
        )
        if end_date and next_dt > end_date:
            break
        results.append(next_dt.strftime("%Y-%m-%d %H:%M:%S"))
        # Step forward slightly to avoid re-evaluating exact same second
        current_dt = next_dt + timedelta(seconds=1)

    return results

def apply_missed_execution_policy(
    due_windows: List[datetime],
    policy: str = "Skip missed executions"
) -> Tuple[List[datetime], List[datetime]]:
    """
    Filters due execution windows according to the configured missed execution policy.
    Returns: (planned_windows, skipped_windows)
    """
    if not due_windows:
        return [], []

    policy_norm = (policy or "Skip missed executions").strip().lower()

    if policy_norm in ("skip missed executions", "skip"):
        # Skip all past due windows; return empty plan
        return [], due_windows
    elif policy_norm in ("catch up latest only", "latest only"):
        # Execute only the most recent window
        latest = due_windows[-1]
        skipped = due_windows[:-1]
        return [latest], skipped
    elif policy_norm in ("catch up all", "all"):
        # Execute all windows in chronological order
        return due_windows, []
    else:
        # Default fallback to Skip
        return [], due_windows

def create_execution_plan(template_doc: Any, current_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Evaluates a single template and generates an execution plan.
    Determines due windows, checks idempotency keys, applies missed execution policy,
    and computes the next future execution date.
    """
    now_dt = current_dt or now_datetime()
    template_name = template_doc.name
    recurrence_type = template_doc.recurrence_type
    tz_str = getattr(template_doc, "execution_timezone", "Asia/Kolkata")
    cron_expr = getattr(template_doc, "cron_expression", None)
    policy = getattr(template_doc, "missed_execution_policy", "Skip missed executions")
    end_date = get_datetime(template_doc.end_date) if getattr(template_doc, "end_date", None) else None

    next_dt = get_datetime(template_doc.next_execution_date or template_doc.start_date)

    due_windows = []
    # Collect all windows that fell due up to now_dt
    while next_dt <= now_dt:
        if end_date and next_dt > end_date:
            break
        
        idempotency_key = compute_idempotency_key(template_name, next_dt)
        if not is_window_executed(idempotency_key):
            due_windows.append(next_dt)
        
        next_dt = calculate_next_execution(
            recurrence_type=recurrence_type,
            from_dt=next_dt + timedelta(seconds=1),
            execution_timezone=tz_str,
            cron_expression=cron_expr
        )

    # Apply missed execution policy
    planned_windows, skipped_windows = apply_missed_execution_policy(due_windows, policy)

    idempotency_keys = [compute_idempotency_key(template_name, dt) for dt in planned_windows]

    return {
        "template_name": template_name,
        "due_windows": [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in due_windows],
        "planned_windows": [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in planned_windows],
        "skipped_windows": [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in skipped_windows],
        "idempotency_keys": idempotency_keys,
        "next_execution_date": next_dt.strftime("%Y-%m-%d %H:%M:%S")
    }

def _acquire_redis_lock(cache, key: str, ttl: int) -> bool:
    if hasattr(cache, "make_key") and hasattr(cache, "set"):
        redis_key = cache.make_key(key)
        return bool(cache.set(redis_key, "locked", ex=ttl, nx=True))
    elif hasattr(cache, "set_value"):
        try:
            return bool(cache.set_value(key, "locked", expires_in_sec=ttl, nx=True))
        except TypeError:
            return bool(cache.set_value(key, "locked", expires_in_sec=ttl))
    return True

def evaluate_recurring_templates(current_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Main scheduler entry point. Scans active templates, acquires distributed locks,
    generates execution plans, updates template next_execution_date, and logs results.
    """
    logger = frappe.logger("tap_buddy_recurring")
    now_dt = current_dt or now_datetime()

    # 1. Acquire Global Scheduler Lock
    if hasattr(frappe, "cache") and frappe.cache():
        acquired = _acquire_redis_lock(frappe.cache(), GLOBAL_LOCK_KEY, GLOBAL_LOCK_TTL)
        if not acquired:
            logger.warning("[RECURRING SCHEDULER] Global lock active. Skipping concurrent execution cycle.")
            return {"status": "SKIPPED_LOCKED", "scanned": 0, "plans": []}

    try:
        templates = frappe.get_all(
            "Recurring Campaign Template",
            filters={
                "status": "Active",
                "next_execution_date": ["<=", now_dt]
            },
            fields=["name"]
        )

        logger.info(f"[RECURRING SCHEDULER] Cycle started at {now_dt}. Due templates found: {len(templates)}")

        plans = []
        for row in templates:
            t_name = row.name
            t_lock_key = f"tap_buddy:recurring_template_lock:{t_name}"
            
            # Per-template lock
            if hasattr(frappe, "cache") and frappe.cache():
                t_locked = _acquire_redis_lock(frappe.cache(), t_lock_key, TEMPLATE_LOCK_TTL)
                if not t_locked:
                    logger.warning(f"[RECURRING SCHEDULER] Template {t_name} locked by another worker. Skipping.")
                    continue

            try:
                if hasattr(frappe.db, "savepoint"):
                    frappe.db.savepoint("eval_template_sp")

                doc = frappe.get_doc("Recurring Campaign Template", t_name)
                plan = create_execution_plan(doc, current_dt=now_dt)

                # Blocker 1: Invoke CampaignGenerationService.generate_from_plan()
                from tap_buddy.services.campaign_generation import CampaignGenerationService
                created_campaigns = CampaignGenerationService.generate_from_plan(doc, plan)
                plan["created_campaigns"] = created_campaigns

                # Blocker 2: Update next_execution_date ONLY after campaign generation succeeds
                if plan.get("status") != "FAILED" and plan.get("next_execution_date"):
                    frappe.db.set_value("Recurring Campaign Template", t_name, "next_execution_date", plan["next_execution_date"])
                    frappe.db.set_value("Recurring Campaign Template", t_name, "last_execution_date", now_dt.strftime("%Y-%m-%d %H:%M:%S"))

                if hasattr(frappe.db, "commit"):
                    frappe.db.commit()

                plans.append(plan)

                logger.info(
                    f"[RECURRING SCHEDULER] Template: {t_name} | "
                    f"Due: {len(plan['due_windows'])} | Planned: {len(plan['planned_windows'])} | "
                    f"Created: {len(created_campaigns)} | Next: {plan['next_execution_date']}"
                )
            except Exception as e:
                if hasattr(frappe.db, "rollback"):
                    frappe.db.rollback()
                logger.error(f"[RECURRING SCHEDULER ERROR] Failed evaluating template {t_name}: {e}")
            finally:
                if hasattr(frappe, "cache") and frappe.cache():
                    frappe.cache().delete_value(t_lock_key)

        return {"status": "SUCCESS", "scanned": len(templates), "plans": plans}

    finally:
        if hasattr(frappe, "cache") and frappe.cache():
            frappe.cache().delete_value(GLOBAL_LOCK_KEY)
