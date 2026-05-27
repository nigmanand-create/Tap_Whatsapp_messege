"""
Unit tests for tap_buddy.services.redis_utils

Tests cover:
  - Token bucket correctness (rate limiting)
  - Distributed lock acquire/release semantics
  - Circuit breaker open/close behaviour
  - Queue push/pop FIFO ordering
  - Atomic batch pop with Lua script

All Redis calls are exercised against a real fakeredis instance so the
Lua scripts are evaluated correctly. No live Redis or Frappe connection
is required.
"""
import json

import pytest

try:
    import fakeredis

    FAKEREDIS_AVAILABLE = True
except ImportError:
    FAKEREDIS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FAKEREDIS_AVAILABLE,
    reason="fakeredis not installed — run: pip install fakeredis",
)


# ---------------------------------------------------------------------------
# Shared fixture: a fake Redis connection patched into redis_utils
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_redis(monkeypatch):
    """
    Patches get_redis_conn() to return a clean fakeredis instance.
    Also patches frappe.parse_json / frappe.as_json with real JSON calls.
    """
    import fakeredis
    server = fakeredis.FakeRedis(decode_responses=True)

    import tap_buddy.services.redis_utils as ru

    monkeypatch.setattr(ru, "get_redis_conn", lambda: server)

    # Patch frappe helpers used inside redis_utils
    import types
    fake_frappe = types.SimpleNamespace(
        as_json=json.dumps,
        parse_json=json.loads,
    )
    monkeypatch.setattr(ru, "frappe", fake_frappe)

    return server


# ---------------------------------------------------------------------------
# 1. Distributed lock
# ---------------------------------------------------------------------------

class TestDistributedLock:
    def test_acquire_lock_returns_true_first_time(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import acquire_lock
        assert acquire_lock("test_lock", timeout=5) is True

    def test_acquire_same_lock_twice_returns_false(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import acquire_lock
        acquire_lock("test_lock2", timeout=5)
        result = acquire_lock("test_lock2", timeout=5)
        assert not result

    def test_release_lock_allows_re_acquire(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import acquire_lock, release_lock
        acquire_lock("test_lock3", timeout=5)
        release_lock("test_lock3")
        assert acquire_lock("test_lock3", timeout=5) is True

    def test_different_lock_names_are_independent(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import acquire_lock
        assert acquire_lock("lock_alpha", timeout=5) is True
        assert acquire_lock("lock_beta", timeout=5) is True


# ---------------------------------------------------------------------------
# 2. Token bucket (rate limiter)
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_consume_within_limit_returns_true(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import consume_token_bucket
        for _ in range(5):
            assert consume_token_bucket("bucket_a", limit=5, window_seconds=60) is True

    def test_consume_exceeds_limit_returns_false(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import consume_token_bucket
        for _ in range(5):
            consume_token_bucket("bucket_b", limit=5, window_seconds=60)
        # 6th call should be rejected
        result = consume_token_bucket("bucket_b", limit=5, window_seconds=60)
        assert result is False

    def test_zero_limit_always_allows(self, fake_redis, monkeypatch):
        """limit=0 means disabled — always pass through."""
        from tap_buddy.services.redis_utils import consume_token_bucket
        for _ in range(100):
            assert consume_token_bucket("bucket_c", limit=0) is True

    def test_different_buckets_are_independent(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import consume_token_bucket
        for _ in range(3):
            consume_token_bucket("bucket_x", limit=3, window_seconds=60)
        # bucket_x is now full but bucket_y should still work
        assert consume_token_bucket("bucket_y", limit=3, window_seconds=60) is True
        assert consume_token_bucket("bucket_x", limit=3, window_seconds=60) is False


# ---------------------------------------------------------------------------
# 3. Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def test_circuit_starts_closed(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import check_circuit_breaker
        assert check_circuit_breaker("glific") is False

    def test_circuit_opens_after_threshold(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import check_circuit_breaker, record_api_failure
        for _ in range(5):
            record_api_failure("glific_cb", reset_timeout=300)
        assert check_circuit_breaker("glific_cb", failure_threshold=5) is True

    def test_circuit_stays_closed_below_threshold(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import check_circuit_breaker, record_api_failure
        for _ in range(4):
            record_api_failure("glific_safe", reset_timeout=300)
        assert check_circuit_breaker("glific_safe", failure_threshold=5) is False

    def test_success_resets_circuit(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import (
            check_circuit_breaker,
            record_api_failure,
            record_api_success,
        )
        for _ in range(5):
            record_api_failure("glific_reset", reset_timeout=300)
        assert check_circuit_breaker("glific_reset", failure_threshold=5) is True

        record_api_success("glific_reset")
        assert check_circuit_breaker("glific_reset", failure_threshold=5) is False


# ---------------------------------------------------------------------------
# 4. Queue — push/pop FIFO ordering
# ---------------------------------------------------------------------------

class TestQueue:
    def test_empty_queue_returns_empty_list(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import pop_from_queue_batch
        result = pop_from_queue_batch("empty_queue", batch_size=10)
        assert result == []

    def test_push_then_pop_returns_item(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import pop_from_queue_batch, push_to_queue
        push_to_queue("q1", {"msg": "hello"})
        result = pop_from_queue_batch("q1", batch_size=10)
        assert len(result) == 1
        assert result[0]["msg"] == "hello"

    def test_queue_is_drained_after_pop(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import pop_from_queue_batch, push_to_queue
        push_to_queue("q2", {"x": 1})
        pop_from_queue_batch("q2", batch_size=10)
        # Second pop should return empty
        result = pop_from_queue_batch("q2", batch_size=10)
        assert result == []

    def test_fifo_ordering_preserved(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import pop_from_queue_batch, push_to_queue
        for i in range(5):
            push_to_queue("q_fifo", {"seq": i})
        result = pop_from_queue_batch("q_fifo", batch_size=10)
        seqs = [r["seq"] for r in result]
        assert seqs == list(range(5)), f"Expected FIFO order, got {seqs}"

    def test_batch_size_limits_pop(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import pop_from_queue_batch, push_to_queue
        for i in range(10):
            push_to_queue("q_batch", {"i": i})
        result = pop_from_queue_batch("q_batch", batch_size=4)
        assert len(result) == 4
        # Remaining 6 should still be in queue
        remaining = pop_from_queue_batch("q_batch", batch_size=100)
        assert len(remaining) == 6

    def test_separate_queues_are_independent(self, fake_redis, monkeypatch):
        from tap_buddy.services.redis_utils import pop_from_queue_batch, push_to_queue
        push_to_queue("qa", {"src": "a"})
        push_to_queue("qb", {"src": "b"})
        result_a = pop_from_queue_batch("qa", batch_size=10)
        result_b = pop_from_queue_batch("qb", batch_size=10)
        assert result_a[0]["src"] == "a"
        assert result_b[0]["src"] == "b"

    def test_malformed_json_routed_to_dlq(self, fake_redis, monkeypatch):
        """A raw non-JSON string in the queue should not crash the batch pop."""
        import tap_buddy.services.redis_utils as ru
        conn = ru.get_redis_conn()
        conn.lpush("tap_buddy:queue:q_poison", "NOT_VALID_JSON{{{")

        result = ru.pop_from_queue_batch("q_poison", batch_size=10)
        # The item should be skipped (routed to DLQ internally), not returned
        assert result == []
