"""Job queue manager with retry and exponential backoff."""

import subprocess
import time
from datetime import datetime, timedelta
from typing import Optional
import logging

from .database import Database
from .models import Job, JobState, Config


logger = logging.getLogger(__name__)


class QueueManager:
    """Manages job queue operations."""
    
    def __init__(self, db: Database):
        """Initialize queue manager."""
        self.db = db
    
    def enqueue_job(self, job: Job) -> None:
        """Add a job to the queue."""
        # Check if job already exists
        existing_job = self.db.get_job(job.id)
        if existing_job:
            raise ValueError(f"Job with id '{job.id}' already exists")
        
        # Get config for max_retries if not set
        if job.max_retries is None:
            config = self.db.get_config()
            job.max_retries = config.max_retries
        
        self.db.save_job(job)
        logger.info(f"Job {job.id} enqueued successfully")
    
    def execute_job(self, job: Job) -> bool:
        """
        Execute a job command.
        Returns True if successful, False otherwise.
        """
        try:
            logger.info(f"Executing job {job.id}: {job.command}")
            
            # Determine timeout
            config = self.db.get_config()
            timeout_sec = job.timeout_seconds if job.timeout_seconds is not None else getattr(config, 'default_timeout_seconds', 300)
            start_ts = datetime.utcnow()
            
            # Execute command with timeout
            result = subprocess.run(
                job.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec
            )
            
            # Capture output (truncate to avoid DB bloat)
            stdout = (result.stdout or '')[:4000]
            stderr = (result.stderr or '')[:4000]
            duration_ms = int((datetime.utcnow() - start_ts).total_seconds() * 1000)
            
            if result.returncode == 0:
                logger.info(f"Job {job.id} completed successfully")
                job.state = JobState.COMPLETED
                job.completed_at = datetime.utcnow()
                job.error_message = None
                job.last_stdout = stdout
                job.last_stderr = stderr
                job.duration_ms = duration_ms
                self.db.save_job(job)
                return True
            else:
                error_msg = stderr or stdout or f"Command exited with code {result.returncode}"
                job.last_stdout = stdout
                job.last_stderr = stderr
                job.duration_ms = duration_ms
                logger.error(f"Job {job.id} failed: {error_msg}")
                self._handle_job_failure(job, error_msg)
                return False
                
        except subprocess.TimeoutExpired:
            error_msg = f"Job execution timed out ({timeout_sec}s)"
            logger.error(f"Job {job.id} timed out")
            self._handle_job_failure(job, error_msg)
            return False
            
        except FileNotFoundError:
            error_msg = "Command not found"
            logger.error(f"Job {job.id} failed: {error_msg}")
            self._handle_job_failure(job, error_msg)
            return False
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Job {job.id} failed with exception: {error_msg}")
            self._handle_job_failure(job, error_msg)
            return False
    
    def _handle_job_failure(self, job: Job, error_message: str) -> None:
        """Handle job failure with retry logic."""
        job.attempts += 1
        job.error_message = error_message
        job.updated_at = datetime.utcnow()
        
        if job.attempts >= job.max_retries:
            # Move to dead letter queue
            logger.warning(f"Job {job.id} exhausted all retries, moving to DLQ")
            job.state = JobState.DEAD
            job.next_retry_at = None
        else:
            # Schedule retry with exponential backoff
            config = self.db.get_config()
            delay_seconds = config.backoff_base ** job.attempts
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            job.state = JobState.FAILED
            logger.info(f"Job {job.id} will retry in {delay_seconds}s (attempt {job.attempts}/{job.max_retries})")
        
        self.db.save_job(job)
    
    def process_retries(self) -> int:
        """
        Process jobs that are ready for retry.
        Returns number of jobs moved to pending.
        """
        retryable_jobs = self.db.get_retryable_jobs()
        count = 0
        
        for job in retryable_jobs:
            job.state = JobState.PENDING
            job.next_retry_at = None
            job.updated_at = datetime.utcnow()
            self.db.save_job(job)
            count += 1
            logger.info(f"Job {job.id} moved to pending for retry")
        
        return count
    
    def get_next_job(self) -> Optional[Job]:
        """Get next job to process (with locking)."""
        return self.db.get_pending_job()
    
    def get_job_status(self, job_id: str) -> Optional[Job]:
        """Get status of a specific job."""
        return self.db.get_job(job_id)
    
    def get_jobs_by_state(self, state: JobState) -> list:
        """Get all jobs with a specific state."""
        return self.db.get_jobs_by_state(state)
    
    def get_all_jobs(self) -> list:
        """Get all jobs."""
        return self.db.get_all_jobs()
    
    def get_statistics(self) -> dict:
        """Get queue statistics."""
        counts = self.db.get_job_counts()
        return {
            'total': sum(counts.values()),
            'pending': counts[JobState.PENDING.value],
            'processing': counts[JobState.PROCESSING.value],
            'completed': counts[JobState.COMPLETED.value],
            'failed': counts[JobState.FAILED.value],
            'dead': counts[JobState.DEAD.value],
        }
    
    def retry_dlq_job(self, job_id: str) -> bool:
        """Retry a job from the dead letter queue."""
        job = self.db.get_job(job_id)
        
        if not job:
            logger.error(f"Job {job_id} not found")
            return False
        
        if job.state != JobState.DEAD:
            logger.error(f"Job {job_id} is not in DLQ (state: {job.state.value})")
            return False
        
        # Reset job for retry
        job.state = JobState.PENDING
        job.attempts = 0
        job.error_message = None
        job.next_retry_at = None
        job.updated_at = datetime.utcnow()
        
        self.db.save_job(job)
        logger.info(f"Job {job_id} moved from DLQ to pending")
        return True
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        return self.db.delete_job(job_id)
