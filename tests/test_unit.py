import os
import sys
import time
import unittest
from datetime import datetime, timedelta

from queuectl.database import Database
from queuectl.models import Job, JobState, Config
from queuectl.queue_manager import QueueManager


TEST_DB = "queuectl_test_unit.db"


class QueueCtlUnitTests(unittest.TestCase):
    def setUp(self):
        # Clean test db
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass
        self.db = Database(TEST_DB)
        self.qm = QueueManager(self.db)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass

    def test_backoff_calculation(self):
        # Set backoff base to 3
        cfg = self.db.get_config()
        cfg.backoff_base = 3
        self.db.save_config(cfg)

        job = Job(id="u-backoff", command="echo noop", max_retries=5)
        self.qm.enqueue_job(job)

        # First failure -> attempts=1, delay=3^1
        self.qm._handle_job_failure(job, "fail1")
        j1 = self.db.get_job("u-backoff")
        self.assertEqual(j1.attempts, 1)
        self.assertEqual(j1.state, JobState.FAILED)
        delay1 = int((j1.next_retry_at - datetime.utcnow()).total_seconds())
        self.assertTrue(2 <= (cfg.backoff_base ** 1) <= 4)  # sanity
        self.assertTrue((cfg.backoff_base ** 1) - 2 <= delay1 <= (cfg.backoff_base ** 1) + 2)

        # Second failure -> attempts=2, delay=3^2
        self.qm._handle_job_failure(j1, "fail2")
        j2 = self.db.get_job("u-backoff")
        self.assertEqual(j2.attempts, 2)
        delay2 = int((j2.next_retry_at - datetime.utcnow()).total_seconds())
        self.assertTrue((cfg.backoff_base ** 2) - 2 <= delay2 <= (cfg.backoff_base ** 2) + 2)

    def test_dlq_boundary(self):
        job = Job(id="u-dlq", command="exit 1", max_retries=2)
        self.qm.enqueue_job(job)
        # Two failures should land in DLQ
        self.qm._handle_job_failure(job, "f1")
        j1 = self.db.get_job("u-dlq")
        self.assertEqual(j1.state, JobState.FAILED)
        self.qm._handle_job_failure(j1, "f2")
        j2 = self.db.get_job("u-dlq")
        self.assertEqual(j2.state, JobState.DEAD)
        self.assertIsNone(j2.next_retry_at)

    def test_run_at_filtering_and_priority(self):
        # Create three jobs: one future, two eligible with different priorities
        now = datetime.utcnow()
        j_future = Job(id="u-future", command="echo future", run_at=now + timedelta(seconds=3600), priority=10)
        j_low = Job(id="u-low", command="echo low", run_at=None, priority=1)
        j_high = Job(id="u-high", command="echo high", run_at=now, priority=5)
        for j in (j_future, j_low, j_high):
            self.qm.enqueue_job(j)
        # get_pending_job should pick u-high first
        picked1 = self.db.get_pending_job()
        self.assertIsNotNone(picked1)
        self.assertEqual(picked1.id, "u-high")
        # Next pending is u-low, future is not eligible
        picked2 = self.db.get_pending_job()
        self.assertIsNotNone(picked2)
        self.assertEqual(picked2.id, "u-low")
        # No more eligible pending
        picked3 = self.db.get_pending_job()
        self.assertIsNone(picked3)

    def test_timeout_behavior(self):
        # A command that sleeps longer than timeout should time out and be marked failed
        # Use python -c to avoid shell-specific sleep
        cmd = "python -c \"import time; time.sleep(5)\""
        job = Job(id="u-timeout", command=cmd, timeout_seconds=1, max_retries=1)
        self.qm.enqueue_job(job)
        j = self.db.get_pending_job()
        self.assertIsNotNone(j)
        ok = self.qm.execute_job(j)
        self.assertFalse(ok)
        j2 = self.db.get_job("u-timeout")
        # Either failed with retry scheduled or dead if max_retries exhausted on first attempt
        self.assertIn(j2.state, (JobState.FAILED, JobState.DEAD))
        # Error message should mention timeout
        self.assertTrue("timed out" in (j2.error_message or "").lower())


if __name__ == "__main__":
    unittest.main()
