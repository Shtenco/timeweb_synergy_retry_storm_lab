"""Transparent deterministic fault injection; fixed before comparing policies."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class FaultPlan:
    requests: int = 360
    incident_start: int = 60
    incident_end: int = 300
    base_delay_ms: float = 4.0
    slow_delay_ms: float = 55.0

    def __post_init__(self) -> None:
        if not (20 <= self.requests <= 20_000):
            raise ValueError("requests must be in 20..20_000")
        if not (0 <= self.incident_start < self.incident_end <= self.requests):
            raise ValueError("incident window must fit requests")
        if not (0 <= self.base_delay_ms <= self.slow_delay_ms <= 500):
            raise ValueError("invalid fault delays")

    def phase(self, request_id: int) -> str:
        if not 0 <= request_id < self.requests:
            raise ValueError("request_id out of range")
        if request_id < self.incident_start:
            return "healthy_before"
        if request_id < self.incident_end:
            return "incident"
        return "healthy_after"

    def category(self, request_id: int) -> str:
        if self.phase(request_id) != "incident":
            return "healthy"
        # Modulo 100, multiplication by a coprime integer: stable varied positions.
        bucket = (request_id * 73 + 29) % 100
        if bucket < 32:
            return "permanent_503"
        if bucket < 64:
            return "transient_503"
        if bucket < 79:
            return "slow_200"
        return "healthy"

    def decision(self, request_id: int, attempt: int) -> tuple[int, float]:
        if attempt < 1 or attempt > 10:
            raise ValueError("attempt must be 1..10")
        kind = self.category(request_id)
        if kind == "permanent_503" or (kind == "transient_503" and attempt == 1):
            return 503, 0.0
        if kind == "slow_200":
            return 200, self.slow_delay_ms / 1000
        return 200, self.base_delay_ms / 1000
