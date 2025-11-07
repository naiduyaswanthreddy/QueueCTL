import os
import time
import unittest
from datetime import datetime, timedelta

from queuectl.database import Database
from queuectl.models import Job, JobState
from queuectl.queue_manager import QueueManager

TEST_DB = "queuectl_test_metrics.db"


class MetricsReaperTests(unittest.TestCase):
    def setUp(self):
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

    def test_metrics_avg_duration_and_completed_last_min(self):
        # Create two completed jobs with durations
        j1 = Job(id="m1", command="echo 1")
        j2 = Job(id="m2", command="echo 2")
        self.qm.enqueue_job(j1)
        self.qm.enqueue_job(j2)
        # Simulate completion
        j1 = self.db.get_job("m1")
        j1.state = JobState.COMPLETED
        j1.completed_at = datetime.utcnow()
        j1.duration_ms = 100
        self.db.save_job(j1)
        j2 = self.db.get_job("m2")
        j2.state = JobState.COMPLETED
        j2.completed_at = datetime.utcnow()
        j2.duration_ms = 300
        self.db.save_job(j2)

        metrics = self.db.get_metrics()
        self.assertEqual(metrics.get("avg_duration_ms"), 200)
        self.assertGreaterEqual(metrics.get("completed_last_min", 0), 2)

    def test_reaper_resets_stale_processing(self):
        # Create a job and mark as processing with old updated_at
        j = Job(id="r1", command="echo r1")
        self.qm.enqueue_job(j)
        j_db = self.db.get_job("r1")
        j_db.state = JobState.PROCESSING
        j_db.updated_at = datetime.utcnow() - timedelta(seconds=1000)
        self.db.save_job(j_db)

        reset = self.db.reset_stale_processing_jobs(stale_seconds=300)
        self.assertEqual(reset, 1)
        j2 = self.db.get_job("r1")
        self.assertEqual(j2.state, JobState.PENDING)


if __name__ == "__main__":
    unittest.main()
