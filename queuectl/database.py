"""Database layer for persistent storage using SQLite."""

import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from contextlib import contextmanager

from .models import Job, JobState, Config


class Database:
    """SQLite database manager for job persistence."""
    
    def __init__(self, db_path: str = "queuectl.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def _get_cursor(self):
        """Get database cursor with automatic commit/rollback."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT,
                next_retry_at TEXT,
                completed_at TEXT,
                priority INTEGER DEFAULT 0,
                run_at TEXT,
                timeout_seconds INTEGER,
                last_stdout TEXT,
                last_stderr TEXT,
                duration_ms INTEGER
            )
        """)
        
        # Create config table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Create workers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id TEXT PRIMARY KEY,
                pid INTEGER,
                name TEXT,
                started_at TEXT NOT NULL,
                last_heartbeat TEXT NOT NULL,
                stopped_at TEXT
            )
        """)
        
        # Create basic indexes that rely on always-present columns
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_job_state 
            ON jobs(state)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_next_retry 
            ON jobs(next_retry_at)
        """)
        conn.commit()

        # Ensure columns exist for upgrades (SQLite: add missing columns) BEFORE creating indexes on them
        self._ensure_job_columns([
            ("priority", "INTEGER", "0"),
            ("run_at", "TEXT", "NULL"),
            ("timeout_seconds", "INTEGER", "NULL"),
            ("last_stdout", "TEXT", "NULL"),
            ("last_stderr", "TEXT", "NULL"),
            ("duration_ms", "INTEGER", "NULL"),
        ])

        # Now that columns are ensured, create indexes that reference them
        cursor = conn.cursor()
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_run_at 
            ON jobs(run_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_priority 
            ON jobs(priority)
        """)
        conn.commit()

    def _ensure_job_columns(self, columns):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(jobs)")
        existing = {row[1] for row in cursor.fetchall()}
        for name, coltype, default in columns:
            if name not in existing:
                if default == "NULL":
                    cursor.execute(f"ALTER TABLE jobs ADD COLUMN {name} {coltype}")
                else:
                    cursor.execute(f"ALTER TABLE jobs ADD COLUMN {name} {coltype} DEFAULT {default}")
        conn.commit()
    
    def save_job(self, job: Job) -> None:
        """Save or update a job."""
        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO jobs 
                (id, command, state, attempts, max_retries, created_at, 
                 updated_at, error_message, next_retry_at, completed_at,
                 priority, run_at, timeout_seconds, last_stdout, last_stderr, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id,
                job.command,
                job.state.value,
                job.attempts,
                job.max_retries,
                job.created_at.isoformat(),
                job.updated_at.isoformat(),
                job.error_message,
                job.next_retry_at.isoformat() if job.next_retry_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                job.priority,
                job.run_at.isoformat() if job.run_at else None,
                job.timeout_seconds,
                job.last_stdout,
                job.last_stderr,
                job.duration_ms,
            ))
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        
        if row:
            return self._row_to_job(row)
        return None
    
    def get_jobs_by_state(self, state: JobState) -> List[Job]:
        """Get all jobs with a specific state."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM jobs WHERE state = ? ORDER BY created_at",
            (state.value,)
        )
        return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def get_all_jobs(self) -> List[Job]:
        """Get all jobs."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
        return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def get_pending_job(self) -> Optional[Job]:
        """Get next pending job and mark it as processing (with lock)."""
        with self._get_cursor() as cursor:
            # Get the highest priority eligible pending job (run_at <= now or NULL)
            cursor.execute("""
                SELECT * FROM jobs 
                WHERE state = ? AND (run_at IS NULL OR run_at <= ?)
                ORDER BY priority DESC, created_at ASC 
                LIMIT 1
            """, (JobState.PENDING.value, datetime.utcnow().isoformat()))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            job = self._row_to_job(row)
            
            # Mark as processing
            job.state = JobState.PROCESSING
            job.updated_at = datetime.utcnow()
            
            cursor.execute("""
                UPDATE jobs 
                SET state = ?, updated_at = ?
                WHERE id = ? AND state = ?
            """, (
                JobState.PROCESSING.value,
                job.updated_at.isoformat(),
                job.id,
                JobState.PENDING.value
            ))
            
            # Check if update was successful (no race condition)
            if cursor.rowcount == 0:
                return None
            
            return job
    
    def get_retryable_jobs(self) -> List[Job]:
        """Get jobs that are ready for retry."""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            SELECT * FROM jobs 
            WHERE state = ? AND next_retry_at <= ?
            ORDER BY next_retry_at
        """, (JobState.FAILED.value, now))
        
        return [self._row_to_job(row) for row in cursor.fetchall()]
    
    def get_job_counts(self) -> dict:
        """Get count of jobs by state."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT state, COUNT(*) as count 
            FROM jobs 
            GROUP BY state
        """)
        
        counts = {state.value: 0 for state in JobState}
        for row in cursor.fetchall():
            counts[row['state']] = row['count']
        
        return counts
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0
    
    def save_config(self, config: Config) -> None:
        """Save configuration."""
        with self._get_cursor() as cursor:
            for key, value in config.to_dict().items():
                cursor.execute("""
                    INSERT OR REPLACE INTO config (key, value)
                    VALUES (?, ?)
                """, (key, json.dumps(value)))
    
    def get_config(self) -> Config:
        """Get configuration."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM config")
        
        config_dict = {}
        for row in cursor.fetchall():
            config_dict[row['key']] = json.loads(row['value'])
        
        if not config_dict:
            # Return default config
            config = Config()
            self.save_config(config)
            return config
        
        return Config(**config_dict)
    
    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job object."""
        return Job(
            id=row['id'],
            command=row['command'],
            state=JobState(row['state']),
            attempts=row['attempts'],
            max_retries=row['max_retries'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            error_message=row['error_message'],
            next_retry_at=datetime.fromisoformat(row['next_retry_at']) if row['next_retry_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            priority=row['priority'] if 'priority' in row.keys() else 0,
            run_at=datetime.fromisoformat(row['run_at']) if row['run_at'] else None,
            timeout_seconds=row['timeout_seconds'] if 'timeout_seconds' in row.keys() else 300,
            last_stdout=row['last_stdout'] if 'last_stdout' in row.keys() else None,
            last_stderr=row['last_stderr'] if 'last_stderr' in row.keys() else None,
            duration_ms=row['duration_ms'] if 'duration_ms' in row.keys() else None,
        )

    def get_metrics(self) -> dict:
        """Compute basic metrics: avg duration of last 20 completed jobs, completed last minute."""
        conn = self._get_connection()
        c = conn.cursor()
        metrics = {"avg_duration_ms": None, "completed_last_min": 0}
        try:
            c.execute("SELECT AVG(duration_ms) as avg_ms FROM (SELECT duration_ms FROM jobs WHERE state = ? AND duration_ms IS NOT NULL ORDER BY completed_at DESC LIMIT 20)", (JobState.COMPLETED.value,))
            row = c.fetchone()
            if row and row[0] is not None:
                metrics["avg_duration_ms"] = int(row[0])
        except Exception:
            pass
        try:
            # Count jobs completed in the last 60 seconds using SQL time math
            # julianday('now') - julianday(completed_at) returns days; convert to seconds
            c.execute(
                """
                SELECT COUNT(*)
                FROM jobs
                WHERE state = ?
                  AND completed_at IS NOT NULL
                  AND ((julianday('now') - julianday(completed_at)) * 86400) <= 60
                """,
                (JobState.COMPLETED.value,)
            )
            row = c.fetchone()
            if row and row[0] is not None:
                metrics["completed_last_min"] = int(row[0])
        except Exception:
            pass
        return metrics
    
    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')

    # -------------------- Workers APIs --------------------
    def register_worker(self, worker_id: str, pid: int, name: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO workers (id, pid, name, started_at, last_heartbeat, stopped_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (worker_id, pid, name, now, now)
            )

    def heartbeat_worker(self, worker_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_cursor() as cursor:
            cursor.execute(
                "UPDATE workers SET last_heartbeat = ? WHERE id = ?",
                (now, worker_id)
            )

    def stop_worker(self, worker_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_cursor() as cursor:
            cursor.execute(
                "UPDATE workers SET stopped_at = ?, last_heartbeat = ? WHERE id = ?",
                (now, now, worker_id)
            )

    def get_active_workers(self, stale_seconds: int = 10) -> int:
        """Return count of active workers whose last_heartbeat is within stale_seconds and not stopped."""
        conn = self._get_connection()
        cursor = conn.cursor()
        threshold = datetime.utcnow().timestamp() - stale_seconds
        # Compare as strings by converting to timestamps in Python
        cursor.execute("SELECT last_heartbeat, stopped_at FROM workers")
        count = 0
        for row in cursor.fetchall():
            if row['stopped_at']:
                continue
            try:
                ts = datetime.fromisoformat(row['last_heartbeat']).timestamp()
                if ts >= threshold:
                    count += 1
            except Exception:
                pass
        return count

    def list_workers(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workers ORDER BY started_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    # -------------------- Maintenance --------------------
    def reset_stale_processing_jobs(self, stale_seconds: int = 300) -> int:
        """Reset jobs stuck in 'processing' back to 'pending' if updated_at is older than stale_seconds.
        Returns number of jobs reset.
        """
        threshold_ts = datetime.utcnow().timestamp() - stale_seconds
        now_iso = datetime.utcnow().isoformat()
        with self._get_cursor() as cursor:
            # Fetch candidate jobs to evaluate timestamps reliably
            cursor.execute("SELECT id, updated_at FROM jobs WHERE state = ?", (JobState.PROCESSING.value,))
            to_reset = []
            for row in cursor.fetchall():
                try:
                    ts = datetime.fromisoformat(row['updated_at']).timestamp()
                    if ts <= threshold_ts:
                        to_reset.append(row['id'])
                except Exception:
                    continue
            count = 0
            for jid in to_reset:
                cursor.execute(
                    "UPDATE jobs SET state = ?, updated_at = ?, error_message = COALESCE(error_message, 'Recovered from stale processing') WHERE id = ?",
                    (JobState.PENDING.value, now_iso, jid)
                )
                if cursor.rowcount:
                    count += 1
            return count
