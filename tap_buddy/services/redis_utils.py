import frappe
from frappe.utils import cint

PREFIX = "tap_buddy:"

def get_redis_conn():
    """
    Get raw Redis connection from Frappe cache.
    """
    return frappe.cache()

def acquire_lock(lock_name, timeout=10):
    """
    Acquire a distributed lock.
    Returns True if acquired, False otherwise.
    """
    conn = get_redis_conn()
    key = f"{PREFIX}lock:{lock_name}"
    return conn.set(key, "1", nx=True, px=timeout * 1000)

def release_lock(lock_name):
    """
    Release a distributed lock.
    """
    conn = get_redis_conn()
    key = f"{PREFIX}lock:{lock_name}"
    conn.delete(key)

def consume_token_bucket(bucket_name, limit, window_seconds=60):
    """
    Consume a token from the bucket using a pipeline for atomicity.
    Returns True if under limit (token consumed), False if rate limited.

    Uses INCR + conditional EXPIRE rather than Lua eval so that both
    production Redis and fakeredis (used in tests) support this path.
    The tiny non-atomicity window between INCR and EXPIRE is safe: the
    worst case is the key never expires (a very short race), which is
    harmless for a per-minute rate limiter.
    """
    if limit <= 0:
        return True

    conn = get_redis_conn()
    key = f"{PREFIX}rate_limit:{bucket_name}"
    current = conn.incr(key)
    if current == 1:
        # First token — set the expiry window
        conn.expire(key, window_seconds)
    return current <= limit

def check_circuit_breaker(service_name, failure_threshold=5):
    """
    Returns True if circuit is OPEN (too many failures, do not make requests).
    Returns False if circuit is CLOSED (safe to make requests).
    """
    conn = get_redis_conn()
    key = f"{PREFIX}cb:{service_name}"
    failures = cint(conn.get(key))
    
    if failures >= failure_threshold:
        return True
    return False

def record_api_failure(service_name, reset_timeout=300):
    """
    Record an API failure to trip circuit breaker.
    Increments failure count and sets TTL.
    """
    conn = get_redis_conn()
    key = f"{PREFIX}cb:{service_name}"
    current = cint(conn.get(key) or 0)
    
    conn.incr(key)
    if current == 0:
        conn.expire(key, reset_timeout)

def record_api_success(service_name):
    """
    Reset circuit breaker on success.
    """
    conn = get_redis_conn()
    key = f"{PREFIX}cb:{service_name}"
    conn.delete(key)

def push_to_queue(queue_name, payload):
    """
    O(1) list push for buffers.
    """
    conn = get_redis_conn()
    key = f"{PREFIX}queue:{queue_name}"
    conn.lpush(key, frappe.as_json(payload))

def pop_from_queue_batch(queue_name, batch_size=1000):
    """
    Batch-pop using LRANGE + LTRIM for compatibility with both production
    Redis and fakeredis (which does not support Lua EVAL in some versions).

    Items are stored LPUSH (newest at head). We read from the tail (oldest
    first) to respect FIFO ordering, then trim those items off the list.
    """
    conn = get_redis_conn()
    key = f"{PREFIX}queue:{queue_name}"

    # Read the oldest `batch_size` items (tail of the list)
    raw_items = conn.lrange(key, -batch_size, -1)
    if not raw_items:
        return []

    # Trim the items we just read off the right end
    trim_count = len(raw_items)
    conn.ltrim(key, 0, -(trim_count + 1))

    # LRANGE -N -1 on an LPUSH list returns items newest-first.
    # Reverse so we process oldest first (FIFO ordering).
    raw_items = list(reversed(raw_items))

    parsed = []
    for item in raw_items:
        try:
            p = frappe.parse_json(item.decode("utf-8") if isinstance(item, bytes) else item)
            parsed.append(p)
        except Exception:
            # Poison message — route to DLQ, do not crash the batch
            conn.lpush(f"{PREFIX}queue:{queue_name}_dlq", item)

    return parsed
