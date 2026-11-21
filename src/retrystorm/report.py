"""Write machine-readable raw results and integrity hashes."""
from __future__ import annotations
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics


def write_benchmark(payload: dict, output: Path) -> dict:
    output.mkdir(parents=True,exist_ok=True)
    results = dict(payload)
    op_rows = results.pop("operation_rows")
    backend_rows = results.pop("backend_events")
    (output/"benchmark.json").write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (output/"operations.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(op_rows[0]))
        w.writeheader();w.writerows(op_rows)
    with (output/"backend_events.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(backend_rows[0]))
        w.writeheader();w.writerows(backend_rows)
    grouped: dict[str,list[dict]] = defaultdict(list)
    for r in results["runs"]:
        grouped[r["policy"]].append(r)
    summary=[]
    for name,items in sorted(grouped.items()):
        summary.append(dict(policy=name,n=len(items),
                            median_success_percent=round(statistics.median(x["success_percent"] for x in items),3),
                            min_success_percent=min(x["success_percent"] for x in items),
                            max_success_percent=max(x["success_percent"] for x in items),
                            median_amplification=round(statistics.median(x["amplification"] for x in items),4),
                            median_p95_ms=round(statistics.median(x["p95_ms"] for x in items),3),
                            median_backend_overload=round(statistics.median(x["backend_overload"] for x in items),1),
                            median_breaker_rejects=round(statistics.median(x["breaker_rejects"] for x in items),1)))
    with (output/"summary.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]))
        w.writeheader();w.writerows(summary)
    # File hashes, so any later article can point to exact inputs rather than a paraphrase.
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob("*")) if p.is_file() and p.name!="SHA256SUMS.json"}
    (output/"SHA256SUMS.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return dict(summary=summary,manifest=manifest)


def verify_output(output: Path) -> dict:
    manifest=json.loads((output/"SHA256SUMS.json").read_text(encoding="utf-8"))
    for filename, digest in manifest.items():
        actual=hashlib.sha256((output/filename).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"SHA256 mismatch: {filename}")
    obj=json.loads((output/"benchmark.json").read_text(encoding="utf-8"))
    with (output/"operations.csv").open(encoding="utf-8",newline="") as f:
        ops=list(csv.DictReader(f))
    with (output/"backend_events.csv").open(encoding="utf-8",newline="") as f:
        events=list(csv.DictReader(f))
    if len(ops)!=obj["benchmark_config"]["requests"]*obj["benchmark_config"]["repeats"]*len(obj["policies"]):
        raise ValueError("operation count mismatch")
    if len(events)!=sum(int(x["attempts"]) for x in ops):
        raise ValueError("backend attempts mismatch")
    for run in obj["runs"]:
        key=lambda x:x["policy"]==run["policy"] and int(x["repeat"])==run["repeat"]
        matching=[x for x in ops if key(x)]
        if len(matching)!=run["requests"] or len(set(int(x["request_id"]) for x in matching))!=run["requests"]:
            raise ValueError("missing/duplicate operation in run")
        if sum(x["success"]=="True" for x in matching)!=run["successes"]:
            raise ValueError("success mismatch")
    return dict(valid=True,files=len(manifest),operations=len(ops),http_calls=len(events),cases=len(obj["runs"]))
