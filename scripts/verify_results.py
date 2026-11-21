#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from retrystorm.report import verify_output

if __name__=="__main__":
    if len(sys.argv)!=2:
        sys.exit("Usage: python scripts/verify_results.py results/experiment_18")
    print(verify_output(Path(sys.argv[1])))
