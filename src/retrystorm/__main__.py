"""Run from any machine: PYTHONPATH=src python -m retrystorm ..."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .load import BenchmarkConfig, benchmark
from .report import write_benchmark, verify_output


def main() -> None:
    p=argparse.ArgumentParser(description="Localhost HTTP retry storm research. Never contacts public network.")
    p.add_argument("--requests",type=int,default=360)
    p.add_argument("--repeats",type=int,default=3)
    p.add_argument("--rps",type=float,default=240)
    p.add_argument("--workers",type=int,default=32)
    p.add_argument("--backend-capacity",type=int,default=8)
    p.add_argument("--seed",type=int,default=41)
    p.add_argument("--output",type=Path,default=Path("results/experiment_18"))
    args=p.parse_args()
    cfg=BenchmarkConfig(requests=args.requests,repeats=args.repeats,offered_rps=args.rps,
                        workers=args.workers,backend_capacity=args.backend_capacity,seed=args.seed)
    def progress(run:dict) -> None:
        print(f"{run['policy']:15s} rep={run['repeat']+1}: success={run['success_percent']:5.1f}% "
              f"amp={run['amplification']:.2f} p95={run['p95_ms']:.1f}ms overload={run['backend_overload']}",flush=True)
    output=write_benchmark(benchmark(cfg,on_case=progress),args.output)
    check=verify_output(args.output)
    print(json.dumps({"output":str(args.output),"verification":check,
                      "summary":output["summary"]},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
