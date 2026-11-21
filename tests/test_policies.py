import threading
import unittest
from retrystorm.policies import CircuitBreaker, RetryBudget, stable_jitter_ms, PolicyRunner, POLICIES

class PolicyTests(unittest.TestCase):
    def test_breaker_half_open_and_recovery(self):
        b=CircuitBreaker(window=4, minimum=3,failure_fraction=.75,cooldown_s=.1)
        now=100.0
        for _ in range(3):
            permit=b.allow(now)
            self.assertTrue(permit)
            b.record(False,permit,now)
        self.assertEqual(b.snapshot()["state"],"open")
        self.assertFalse(b.allow(now+.01))
        permit=b.allow(now+.11)
        self.assertTrue(permit)
        self.assertFalse(b.allow(now+.12))
        b.record(True,permit,now+.13)
        self.assertEqual(b.snapshot()["state"],"closed")

    def test_late_old_epoch_cannot_close_half_open(self):
        b=CircuitBreaker(window=2,minimum=1,failure_fraction=1.0,cooldown_s=.1)
        stale=b.allow(100.0)
        trigger=b.allow(100.0)
        b.record(False,trigger,100.0)
        probe=b.allow(100.11)
        self.assertTrue(probe.is_probe)
        b.record(True,stale,100.12)
        self.assertEqual(b.snapshot()["state"],"half_open")
        self.assertFalse(b.allow(100.12))
        b.record(True,probe,100.13)
        self.assertEqual(b.snapshot()["state"],"closed")

    def test_local_bulkhead_rejection_does_not_open_breaker(self):
        b=CircuitBreaker(window=2,minimum=1,failure_fraction=1.0,cooldown_s=.1)
        ticket=b.allow(100)
        b.cancel(ticket,100.01)
        self.assertEqual(b.snapshot()["state"],"closed")
        self.assertEqual(b.snapshot()["opens"],0)

    def test_budget_atomic(self):
        b=RetryBudget(2)
        results=[]
        threads=[threading.Thread(target=lambda:results.append(b.take())) for _ in range(20)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(results),2)
        self.assertEqual(b.spent,2)

    def test_jitter_deterministic_bounded(self):
        x=stable_jitter_ms(123,2,41,12)
        self.assertEqual(x,stable_jitter_ms(123,2,41,12))
        self.assertTrue(0 <= x < 24)
        self.assertNotEqual(x,stable_jitter_ms(123,2,42,12))

    def test_disallows_public_endpoint(self):
        with self.assertRaises(ValueError):
            PolicyRunner(POLICIES[0],"https://example.com",20,41)

class ConcurrentBreakerTests(unittest.TestCase):
    def test_single_probe_when_concurrently_half_open(self):
        b=CircuitBreaker(window=2, minimum=1, failure_fraction=1.0, cooldown_s=.1)
        ticket=b.allow(100)
        b.record(False,ticket,100)
        permits=[]
        lock=threading.Lock()
        def try_probe():
            permit=b.allow(100.11)
            with lock:permits.append(permit)
        threads=[threading.Thread(target=try_probe) for _ in range(30)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(x is not None for x in permits),1)
        self.assertEqual(b.snapshot()['half_open_probes'],1)

    def test_six_policy_names_unique(self):
        self.assertEqual(len(POLICIES),6)
        self.assertEqual(len({x.name for x in POLICIES}),6)

    def test_negative_budget_is_not_a_way_to_gain_attempts(self):
        b=RetryBudget(0)
        for _ in range(12):self.assertFalse(b.take())
        self.assertEqual(b.spent,0)

    def test_closed_ignores_obsolete_completion(self):
        b=CircuitBreaker(window=1, minimum=1, failure_fraction=1.0, cooldown_s=.1)
        old=b.allow(50)
        b.record(False,old,50)
        probe=b.allow(50.11)
        b.record(True,probe,50.12)
        b.record(False,old,50.13)
        self.assertEqual(b.snapshot()['state'],'closed')
