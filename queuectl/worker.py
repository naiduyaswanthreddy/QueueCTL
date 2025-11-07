"""Worker process for executing jobs."""

import time
import signal
import sys
import logging
from threading import Thread, Event
from typing import List
import os
import uuid

from .database import Database
from .queue_manager import QueueManager
from .models import Config


logger = logging.getLogger(__name__)


class Worker:
    """Worker that processes jobs from the queue."""
    
    def __init__(self, worker_index: int, db: Database, stop_event: Event):
        """Initialize worker."""
        self.worker_index = worker_index
        self.db = db
        self.queue_manager = QueueManager(db)
        self.stop_event = stop_event
        self.current_job_id = None
        # Compose a unique worker id: hostpid-index-uuid4(short)
        self.worker_id = f"{os.getpid()}-{worker_index}-{str(uuid.uuid4())[:8]}"
    
    def run(self):
        """Main worker loop."""
        logger.info(f"Worker {self.worker_id} started")
        # Register worker
        try:
            self.db.register_worker(self.worker_id, os.getpid(), f"worker-{self.worker_index}")
        except Exception as e:
            logger.error(f"Failed to register worker {self.worker_id}: {e}")
        config = self.db.get_config()
        # Reap stale processing jobs on startup
        try:
            reset = self.db.reset_stale_processing_jobs(stale_seconds=max(int(config.worker_poll_interval) * 120, 300))
            if reset:
                logger.info(f"Worker {self.worker_id} reset {reset} stale processing job(s)")
        except Exception:
            pass
        last_reap = time.time()
        
        while not self.stop_event.is_set():
            try:
                # Heartbeat
                try:
                    self.db.heartbeat_worker(self.worker_id)
                except Exception:
                    pass
                # Periodically reset stale processing jobs (every ~60s)
                if time.time() - last_reap >= 60:
                    try:
                        reset = self.db.reset_stale_processing_jobs(stale_seconds=max(int(config.worker_poll_interval) * 120, 300))
                        if reset:
                            logger.info(f"Worker {self.worker_id} reset {reset} stale processing job(s)")
                    except Exception:
                        pass
                    last_reap = time.time()
                # Process retries first
                self.queue_manager.process_retries()
                
                # Get next job
                job = self.queue_manager.get_next_job()
                
                if job:
                    self.current_job_id = job.id
                    logger.info(f"Worker {self.worker_id} picked up job {job.id}")
                    
                    # Execute job
                    self.queue_manager.execute_job(job)
                    
                    self.current_job_id = None
                else:
                    # No jobs available, sleep
                    time.sleep(config.worker_poll_interval)
                    
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                time.sleep(1)
        
        try:
            self.db.stop_worker(self.worker_id)
        except Exception:
            pass
        logger.info(f"Worker {self.worker_id} stopped")


class WorkerManager:
    """Manages multiple worker threads."""
    
    def __init__(self, db_path: str = "queuectl.db"):
        """Initialize worker manager."""
        self.db_path = db_path
        self.workers: List[Thread] = []
        self.stop_event = Event()
        self.running = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop()
    
    def start(self, worker_count: int = 1):
        """Start worker threads."""
        if self.running:
            logger.warning("Workers already running")
            return
        
        logger.info(f"Starting {worker_count} worker(s)...")
        self.running = True
        self.stop_event.clear()
        
        for i in range(worker_count):
            # Each worker gets its own database connection
            db = Database(self.db_path)
            worker = Worker(i + 1, db, self.stop_event)
            
            thread = Thread(target=worker.run, daemon=False)
            thread.start()
            self.workers.append(thread)
        
        logger.info(f"{worker_count} worker(s) started successfully")
        
        # Wait for all workers to complete
        try:
            for thread in self.workers:
                thread.join()
        except KeyboardInterrupt:
            logger.info("Interrupted, stopping workers...")
            self.stop()
    
    def stop(self):
        """Stop all workers gracefully."""
        if not self.running:
            return
        
        logger.info("Stopping workers gracefully (finishing current jobs)...")
        self.stop_event.set()
        
        # Wait for all workers to finish
        for thread in self.workers:
            thread.join(timeout=30)
        
        self.workers.clear()
        self.running = False
        logger.info("All workers stopped")
    
    def is_running(self) -> bool:
        """Check if workers are running."""
        return self.running and any(thread.is_alive() for thread in self.workers)
    
    def get_worker_count(self) -> int:
        """Get number of active workers."""
        return sum(1 for thread in self.workers if thread.is_alive())


def start_workers(count: int = 1, db_path: str = "queuectl.db"):
    """Start worker processes."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    manager = WorkerManager(db_path)
    
    try:
        manager.start(count)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        manager.stop()
        sys.exit(0)
