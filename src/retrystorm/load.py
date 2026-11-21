"""Concurrent, open-loop offered-load generator against an actual localhost HTTP server.

The arrival sequence is fixed across policies, but OS scheduling is not deterministic.
Each policy gets an isolated server and a fresh fault plan.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from collections import Counter, defaultdict
import math
import platform
import statistics
import sys
import time

from .faults import FaultPlan
from .policies import POLICIES, PolicyConfig, PolicyRunner
from .server import LocalDependency


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    if not 0 <= q <= 100:
        raise ValueError("percentile outside 0..100")
    s = sorted(values)
    pos = (len(s) - 1) * (q / 100)
    low = math.floor(pos)
    high = math.ceil(pos)
    return s[low] if high == low else s[low] + (s[high] - s[low]) * (pos - low)


@dataclass(frozen=True)
class BenchmarkConfig:
    requests: int = 360
    repeats: int = 3
    workers: int = 32
    offered_rps: float = 240.0
    backend_capacity: int = 8
    seed: int = 41

    def __post_init__(self) -> None:
        if not 20 <= self.requests <= 20_000:
            raise ValueError("requests must be 20..20,000")
        if not 1 <= self.repeats <= 20 or not 1 <= self.workers <= 256:
            raise ValueError("invalid repetitions or workers")
        if not 1 <= self.offered_rps <= 10_000:
            raise ValueError("offered_rps outside 1..10,000")
        if not 1 <= self.backend_capacity <= 256:
            raise ValueError("invalid backend capacity")


def run_case(config: BenchmarkConfig, policy: PolicyConfig, repeat: int) -> tuple[list[dict], dict, list[dict]]:
    incident_start = max(5, config.requests // 6)
    incident_end = min(config.requests - 5, (config.requests * 5) // 6)
    plan = FaultPlan(requests=config.requests, incident_start=incident_start,
                     incident_end=incident_end, base_delay_ms=4.0, slow_delay_ms=55.0)
    with LocalDependency(plan, capacity=config.backend_capacity) as backend:
        runner = PolicyRunner(policy, backend.url, config.requests, config.seed+repeat,
                              bulkhead_capacity=config.backend_capacity)
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=config.workers, thread_name_prefix="client") as pool:
            futures = []
            # Keep offered load independent of completion order. Futures may queue when full.
            for i in range(config.requests):
                at = start + i / config.offered_rps
                pause = at - time.monotonic()
                if pause > 0:
                    time.sleep(pause)
                futures.append(pool.submit(runner.operate, i))
            rows = [f.result(timeout=30) for f in futures]
        wall_s = time.monotonic()-start
        # Timed-out client connections can still have in-flight server-side work.
        t_end = time.monotonic() + 1.0
        while backend.telemetry.snapshot()["active_at_snapshot"] and time.monotonic() < t_end:
            time.sleep(0.012)
        snapshot = backend.telemetry.snapshot()

    if len(rows) != config.requests or len({x["request_id"] for x in rows}) != config.requests:
        raise AssertionError("lost or duplicated logical operation")
    if snapshot["counters"].get("received",0) != sum(x["attempts"] for x in rows):
        raise AssertionError("HTTP received count differs from client attempts")
    if snapshot["active_at_snapshot"] != 0:
        raise AssertionError("server still processing when snapshot taken")
    attempt_count = sum(x["attempts"] for x in rows)
    success_count = sum(x["success"] for x in rows)
    all_latency = [x["latency_ms"] for x in rows]
    server_results = snapshot["counters"]
    summary = dict(policy=policy.name, repeat=repeat, seed=config.seed+repeat,
                   requests=config.requests, successes=success_count,
                   success_percent=round(100*success_count/config.requests,3),
                   downstream_attempts=attempt_count,
                   amplification=round(attempt_count/config.requests,4),
                   backend_http_503=server_results.get("status_503",0),
                   backend_overload=server_results.get("overload",0),
                   backend_http_200=server_results.get("status_200",0),
                   max_backend_in_flight=snapshot["max_active"],
                   p50_ms=round(percentile(all_latency,50),3),
                   p95_ms=round(percentile(all_latency,95),3),
                   p99_ms=round(percentile(all_latency,99),3),
                   wall_s=round(wall_s,3),
                   breaker_opens=runner.breaker.snapshot()["opens"] if runner.breaker else 0,
                   breaker_rejects=runner.breaker.snapshot()["rejects"] if runner.breaker else 0,
                   retry_budget_spent=runner.budget.spent if runner.budget else 0,
                   reason_counts=dict(Counter(x["reason"] for x in rows)),
                   phases={})
    for phase in ("healthy_before", "incident", "healthy_after"):
        items = [row for row in rows if plan.phase(row["request_id"])==phase]
        summary["phases"][phase] = dict(requests=len(items),successes=sum(x["success"] for x in items),
                                       attempts=sum(x["attempts"] for x in items),
                                       p95_ms=round(percentile([x["latency_ms"] for x in items],95),3))
    for row in rows:
        row.update(repeat=repeat,phase=plan.phase(row["request_id"]),
                   seed=config.seed+repeat)
    for ev in snapshot["events"]:
        ev.update(repeat=repeat,policy=policy.name)
    return rows, summary, snapshot["events"]


def benchmark(config: BenchmarkConfig, on_case=None) -> dict:
    results, ops, events = [], [], []
    # Rotate policy order across repetitions; mitigates some thermal/order bias.
    for repeat in range(config.repeats):
        sequence = list(POLICIES)
        sequence = sequence[repeat % len(sequence):] + sequence[:repeat % len(sequence)]
        for policy in sequence:
            rows, summary, backend_events = run_case(config, policy, repeat)
            results.append(summary)
            ops.extend(rows)
            events.extend(backend_events)
            if on_case:
                on_case(summary)
    return dict(schema_version="1.0",kind="actual_localhost_http_measurements",
                environment=dict(platform=platform.platform(),python=sys.version.split()[0],
                                 processor=platform.processor(),architecture=platform.machine()),
                benchmark_config=asdict(config),
                fault_model=dict(incident_window="requests/6 to 5*requests/6",
                                 classes="32% permanent 503; 32% first-attempt 503; 15% 55ms slow 200; 21% healthy",
                                 fault_distribution="deterministic modulo 100",
                                 deadline_ms=190,client_timeout_ms=40,
                                 backend_capacity=config.backend_capacity,
                                 test_scope="single host / 127.0.0.1 / HTTP threads; NOT cloud cluster"),
                policies=[asdict(x) for x in POLICIES],runs=results,
                operation_rows=ops,backend_events=events)
