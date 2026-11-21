import unittest
from retrystorm.faults import FaultPlan

class FaultTests(unittest.TestCase):
    def test_phases_and_determinism(self):
        p=FaultPlan(requests=360,incident_start=60,incident_end=300)
        self.assertEqual(p.phase(0),"healthy_before")
        self.assertEqual(p.phase(60),"incident")
        self.assertEqual(p.phase(300),"healthy_after")
        self.assertEqual(p.decision(2,1),p.decision(2,1))
        self.assertEqual(sum(p.category(i)=="permanent_503" for i in range(60,300)) > 0,True)

    def test_transient_then_recovery(self):
        p=FaultPlan(requests=360,incident_start=60,incident_end=300)
        i=next(i for i in range(60,300) if p.category(i)=="transient_503")
        self.assertEqual(p.decision(i,1)[0],503)
        self.assertEqual(p.decision(i,2)[0],200)

    def test_range_guards(self):
        with self.assertRaises(ValueError):
            FaultPlan(requests=19)
        with self.assertRaises(ValueError):
            FaultPlan(requests=20,incident_start=5,incident_end=21)
