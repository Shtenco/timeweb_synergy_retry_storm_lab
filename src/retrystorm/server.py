"""Actual HTTP server with measurable bounded concurrent handling and injected faults."""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
from urllib.parse import urlparse, parse_qs

from .faults import FaultPlan


@dataclass
class ServerTelemetry:
    capacity: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    active: int = 0
    max_active: int = 0
    counters: Counter = field(default_factory=Counter)
    events: list[dict] = field(default_factory=list)

    def enter(self) -> bool:
        with self.lock:
            self.counters["received"] += 1
            if self.active >= self.capacity:
                self.counters["overload"] += 1
                return False
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            return True

    def leave(self) -> None:
        with self.lock:
            self.active -= 1
            assert self.active >= 0

    def record(self, event: dict) -> None:
        with self.lock:
            self.counters[f"status_{event['status']}"] += 1
            self.events.append(event)

    def snapshot(self) -> dict:
        with self.lock:
            return dict(counters=dict(self.counters), max_active=self.max_active,
                        active_at_snapshot=self.active, events=list(self.events))


class LocalDependency:
    """Context manager: binds exclusively to 127.0.0.1 on an ephemeral port."""
    def __init__(self, fault_plan: FaultPlan, capacity: int = 8) -> None:
        if not 1 <= capacity <= 1024:
            raise ValueError("capacity outside allowed range")
        self.plan = fault_plan
        self.telemetry = ServerTelemetry(capacity=capacity)
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.url = ""

    def __enter__(self) -> "LocalDependency":
        plan, telemetry = self.plan, self.telemetry

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                started = time.monotonic()
                parsed = urlparse(self.path)
                q = parse_qs(parsed.query)
                try:
                    if parsed.path != "/v1/health":
                        assert parsed.path == "/v1/work"
                    if parsed.path == "/v1/health":
                        self.reply(200, {"healthy": True})
                        return
                    if set(q) != {"id", "attempt"}:
                        raise ValueError("only id and attempt are accepted")
                    request_id, attempt = int(q["id"][0]), int(q["attempt"][0])
                    phase, category = plan.phase(request_id), plan.category(request_id)
                    status, delay = plan.decision(request_id, attempt)
                except (ValueError, KeyError, AssertionError, IndexError):
                    self.reply(400, {"error": "invalid request"})
                    return

                admitted = telemetry.enter()
                if not admitted:
                    status, delay = 503, 0.0
                try:
                    if delay:
                        time.sleep(delay)
                    telemetry.record({"request_id": request_id, "attempt": attempt,
                                      "phase": phase, "category": category,
                                      "status": status, "overload": not admitted,
                                      "service_ms": round((time.monotonic()-started)*1000, 3)})
                    self.reply(status, {"request_id": request_id,
                                        "attempt": attempt, "ok": status == 200})
                finally:
                    if admitted:
                        telemetry.leave()

            def reply(self, status: int, payload: dict) -> None:
                wire = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(wire)))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(wire)
                except (BrokenPipeError, ConnectionResetError):
                    # A timed-out client may leave before a late server response.
                    pass

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.httpd = Server(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.httpd.server_address
        self.url = f"http://{host}:{port}"
        return self

    def __exit__(self, *_: object) -> None:
        assert self.httpd is not None
        self.httpd.shutdown()
        self.httpd.server_close()
        assert self.thread is not None
        self.thread.join(timeout=3)
