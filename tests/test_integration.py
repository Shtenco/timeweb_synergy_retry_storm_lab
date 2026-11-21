import tempfile
import unittest
from pathlib import Path
from retrystorm.faults import FaultPlan
from retrystorm.server import LocalDependency
from retrystorm.policies import PolicyRunner, POLICIES
from retrystorm.load import BenchmarkConfig, benchmark, percentile
from retrystorm.report import write_benchmark, verify_output

class HttpTests(unittest.TestCase):
    def test_real_http_transient(self):
        p=FaultPlan(requests=60,incident_start=10,incident_end=50)
        i=next(i for i in range(10,50) if p.category(i)=="transient_503")
        with LocalDependency(p,capacity=3) as server:
            r=PolicyRunner(POLICIES[1],server.url,60,41)
            row=r.operate(i)
            self.assertTrue(row["success"])
            self.assertEqual(row["attempts"],2)

    def test_all_policies_end_to_end_and_verification(self):
        cfg=BenchmarkConfig(requests=24,repeats=1,workers=8,offered_rps=100,backend_capacity=4)
        results=benchmark(cfg)
        self.assertEqual(len(results["runs"]),len(POLICIES))
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            write_benchmark(results,output)
            check=verify_output(output)
            self.assertEqual(check["operations"],24*len(POLICIES))
            # Integrity check must reject a modified CSV.
            with (output/"operations.csv").open("a",encoding="utf-8") as f:f.write("tamper\n")
            with self.assertRaises(ValueError):verify_output(output)

    def test_percentile(self):
        self.assertEqual(percentile([1,2,3,4,5],50),3)
        self.assertEqual(percentile([1,3],95),2.9)
