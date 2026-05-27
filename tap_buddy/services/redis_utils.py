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

# Token Bucket Lua Script
# KEYS[1] = bucket key
# ARGV[1] = max tokens (rate limit)
# ARGV[2] = expiration window in seconds
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local current = tonumber(redis.call('get', key) or "0")

if current + 1 > limit then
    return 0
else
    redis.call('incr', key)
    if current == 0 then
        redis.call('expire', key, ARGV[2])
    end
    return 1
end
"""

def consume_token_bucket(bucket_name, limit, window_seconds=60):
    """
    Consume a token from the bucket. 
    Returns True if successful (under limit), False if rate limited.
    """
    if limit <= 0:
        return True
        
    conn = get_redis_conn()
    key = f"{PREFIX}rate_limit:{bucket_name}"
    result = conn.eval(LUA_TOKEN_BUCKET, 1, getattr(conn, "make_key", lambda x: x)(key) if hasattr(conn, "make_key") else key, limit, window_seconds)
    return bool(result)

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

# Atomic multi-pop Lua script
# Pops multiple elements from the right of the list
LUA_POP_BATCH = """
local key = KEYS[1]
local count = tonumber(ARGV[1])
local items = redis.call('LRANGE', key, -count, -1)
if #items > 0 then
    redis.call('LTRIM', key, 0, -#items - 1)
end
return items
"""

def pop_from_queue_batch(queue_name, batch_size=1000):
    """
    Atomic pop using Lua to retrieve a batch of messages.
    Reverses the items to maintain FIFO order since LRANGE -count -1 
    returns older items first (pushed via LPUSH).
    """
    conn = get_redis_conn()
    key = f"{PREFIX}queue:{queue_name}"
    
    result = conn.eval(LUA_POP_BATCH, 1, getattr(conn, "make_key", lambda x: x)(key) if hasattr(conn, "make_key") else key, batch_size)
    if not result:
        return []
        
    # Reverse to process oldest first (FIFO)
    result.reverse()
    
    parsed = []
    for item in result:
        try:
            p = frappe.parse_json(item.decode("utf-8") if isinstance(item, bytes) else item)
            parsed.append(p)
        except Exception:
            # DLQ poison message
            conn.lpush(f"{PREFIX}queue:{queue_name}_dlq", item)
            
    return parsed
