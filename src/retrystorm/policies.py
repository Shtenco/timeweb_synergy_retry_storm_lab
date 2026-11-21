"""Client policies with explicit retry budget, deadline, breaker and bulkhead."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import hashlib
import http.client
import threading
import time
from urllib.parse import urlencode


@dataclass(frozen=True)
class BreakerPermit:
    epoch: int
    is_probe: bool


class CircuitBreaker:
    """CLOSED -> OPEN -> HALF_OPEN with stale-completion fencing.

    Every admitted HTTP call receives an epoch-tagged permit. A late result
    from the previous epoch cannot close a newer half-open probe or reset
    fresh statistics. Under concurrency, only ONE half-open probe is admitted.
    """
    def __init__(self, window: int = 16, minimum: int = 8,
                 failure_fraction: float = 0.60, cooldown_s: float = 0.12) -> None:
        if not (1 <= minimum <= window and 0 < failure_fraction <= 1 and cooldown_s > 0):
            raise ValueError("invalid breaker configuration")
        self.window, self.minimum, self.fraction, self.cooldown = window, minimum, failure_fraction, cooldown_s
        self.history: deque[bool] = deque(maxlen=window)
        self.state = "closed"
        self.open_until = 0.0
        self.probe_reserved = False
        self.lock = threading.Lock()
        self.epoch = 0
        self.opens = 0
        self.rejects = 0
        self.probes = 0

    def allow(self, now: float | None = None) -> BreakerPermit | None:
        now = time.monotonic() if now is None else now
        with self.lock:
            if self.state == "open":
                if now < self.open_until:
                    self.rejects += 1
                    return None
                self.state = "half_open"
                self.probe_reserved = False
            if self.state == "half_open":
                if self.probe_reserved:
                    self.rejects += 1
                    return None
                self.probe_reserved = True
                self.probes += 1
                return BreakerPermit(self.epoch, True)
            return BreakerPermit(self.epoch, False)

    def record(self, success: bool, permit: BreakerPermit, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self.lock:
            if permit.epoch != self.epoch:
                return  # obsolete in-flight work from an earlier breaker generation
            if self.state == "half_open":
                if not permit.is_probe or not self.probe_reserved:
                    return
                self.probe_reserved = False
                if success:
                    self.state = "closed"
                    self.history.clear()
                    self.epoch += 1
                else:
                    self._open(now)
                return
            if self.state != "closed" or permit.is_probe:
                return
            self.history.append(success)
            if (len(self.history) >= self.minimum and
               sum(not x for x in self.history) / len(self.history) >= self.fraction):
                self._open(now)

    def cancel(self, permit: BreakerPermit, now: float | None = None) -> None:
        """A local bulkhead reject is not an upstream failure."""
        now = time.monotonic() if now is None else now
        with self.lock:
            if self.epoch == permit.epoch and self.state == "half_open" and permit.is_probe:
                self.probe_reserved = False
                self.state = "open"
                self.open_until = now + self.cooldown

    def _open(self, now: float) -> None:
        self.state = "open"
        self.open_until = now + self.cooldown
        self.epoch += 1
        self.opens += 1

    def snapshot(self) -> dict:
        with self.lock:
            return dict(state=self.state, opens=self.opens, rejects=self.rejects,
                        half_open_probes=self.probes, epoch=self.epoch)


class RetryBudget:
    def __init__(self, maximum: int) -> None:
        self.remaining = maximum
        self.lock = threading.Lock()
        self.spent = 0

    def take(self) -> bool:
        with self.lock:
            if self.remaining <= 0:
                return False
            self.remaining -= 1
            self.spent += 1
            return True


def stable_jitter_ms(request_id: int, attempt: int, seed: int, base_ms: float) -> float:
    """Deterministic full jitter; not Python's salted hash()."""
    digest = hashlib.sha256(f"{seed}:{request_id}:{attempt}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    return fraction * base_ms * (2 ** (attempt - 1))


@dataclass(frozen=True)
class PolicyConfig:
    name: str
    max_attempts: int
    backoff: bool = False
    breaker: bool = False
    bulkhead: bool = False
    retry_budget_fraction: float = 0.0


POLICIES = (
    PolicyConfig("direct", 1),
    PolicyConfig("naive_retry", 3),
    PolicyConfig("jitter_retry", 3, backoff=True),
    PolicyConfig("breaker_only", 1, breaker=True),
    PolicyConfig("budget_bulkhead", 3, backoff=True, bulkhead=True, retry_budget_fraction=0.30),
    PolicyConfig("protected", 3, backoff=True, breaker=True, bulkhead=True, retry_budget_fraction=0.30),
)


class PolicyRunner:
    def __init__(self, config: PolicyConfig, base_url: str, requests: int, seed: int,
                 per_attempt_timeout_s: float = 0.040, operation_deadline_s: float = 0.190,
                 bulkhead_capacity: int = 8) -> None:
        if not base_url.startswith("http://127.0.0.1:"):
            raise ValueError("Only localhost HTTP is allowed")
        self.config = config
        self.host, self.port = "127.0.0.1", int(base_url.rsplit(":", 1)[1])
        self.seed = seed
        self.timeout = per_attempt_timeout_s
        self.deadline = operation_deadline_s
        self.breaker = CircuitBreaker() if config.breaker else None
        self.bulkhead = threading.BoundedSemaphore(bulkhead_capacity) if config.bulkhead else None
        self.budget = RetryBudget(int(requests * config.retry_budget_fraction)) if config.retry_budget_fraction else None

    def _call(self, request_id: int, attempt: int, timeout: float) -> tuple[int, str]:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            conn.request("GET", "/v1/work?" + urlencode({"id":request_id, "attempt":attempt}))
            response = conn.getresponse()
            status = response.status
            response.read()
            return status, "ok" if status == 200 else "http_503" if status == 503 else "http_other"
        except (TimeoutError, OSError, http.client.HTTPException) as exc:
            return 0, "timeout" if isinstance(exc, (TimeoutError,)) else "transport"
        finally:
            conn.close()

    def operate(self, request_id: int) -> dict:
        start = time.monotonic()
        deadline = start + self.deadline
        attempts = 0
        reason = "unknown"
        retry_count = 0
        for attempt in range(1, self.config.max_attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = "deadline"
                break
            if attempt > 1:
                if self.budget is not None and not self.budget.take():
                    reason = "retry_budget"
                    break
                retry_count += 1
                if self.config.backoff:
                    pause = stable_jitter_ms(request_id, attempt, self.seed, 12.0)/1000
                    if pause >= remaining:
                        reason = "deadline"
                        break
                    time.sleep(pause)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        reason = "deadline"
                        break
            permit = self.breaker.allow() if self.breaker is not None else None
            if self.breaker is not None and permit is None:
                reason = "breaker_open"
                break
            admitted = False
            if self.bulkhead is not None:
                admitted = self.bulkhead.acquire(timeout=min(0.008, max(0,remaining)))
                if not admitted:
                    # Local admission failure must not count as upstream failure.
                    if self.breaker is not None:
                        assert permit is not None
                        self.breaker.cancel(permit)
                    reason = "bulkhead_full"
                    break
            try:
                timeout = min(self.timeout, max(0.001, deadline - time.monotonic()))
                attempts += 1
                status, reason = self._call(request_id, attempt, timeout)
            finally:
                if admitted:
                    assert self.bulkhead is not None
                    self.bulkhead.release()
            if self.breaker is not None:
                assert permit is not None
                self.breaker.record(status == 200, permit)
            if status == 200:
                reason = "ok"
                break
            if reason not in {"http_503", "timeout", "transport"}:
                break
        latency_ms = (time.monotonic() - start) * 1000
        return dict(request_id=request_id, success=reason == "ok", reason=reason,
                    attempts=attempts, retries=retry_count, latency_ms=round(latency_ms, 3),
                    policy=self.config.name)