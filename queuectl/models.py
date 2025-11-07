"""Data models for QueueCTL."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class JobState(Enum):
    """Job state enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"


@dataclass
class Job:
    """Job model representing a background task."""
    id: str
    command: str
    state: JobState = JobState.PENDING
    attempts: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Bonus fields
    priority: int = 0
    run_at: Optional[datetime] = None
    timeout_seconds: Optional[int] = 300
    last_stdout: Optional[str] = None
    last_stderr: Optional[str] = None
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert job to dictionary."""
        return {
            'id': self.id,
            'command': self.command,
            'state': self.state.value,
            'attempts': self.attempts,
            'max_retries': self.max_retries,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'error_message': self.error_message,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'priority': self.priority,
            'run_at': self.run_at.isoformat() if self.run_at else None,
            'timeout_seconds': self.timeout_seconds,
            'last_stdout': self.last_stdout,
            'last_stderr': self.last_stderr,
            'duration_ms': self.duration_ms,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create job from dictionary."""
        return cls(
            id=data['id'],
            command=data['command'],
            state=JobState(data['state']),
            attempts=data['attempts'],
            max_retries=data['max_retries'],
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.utcnow(),
            error_message=data.get('error_message'),
            next_retry_at=datetime.fromisoformat(data['next_retry_at']) if data.get('next_retry_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            priority=int(data.get('priority', 0)),
            run_at=datetime.fromisoformat(data['run_at']) if data.get('run_at') else None,
            timeout_seconds=int(data.get('timeout_seconds', 300)) if data.get('timeout_seconds') is not None else 300,
            last_stdout=data.get('last_stdout'),
            last_stderr=data.get('last_stderr'),
            duration_ms=int(data['duration_ms']) if data.get('duration_ms') is not None else None,
        )


@dataclass
class Config:
    """Configuration model."""
    max_retries: int = 3
    backoff_base: int = 2
    worker_poll_interval: float = 1.0
    # Optional default execution timeout (seconds) for jobs when not set per job
    default_timeout_seconds: int = 300
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            'max_retries': self.max_retries,
            'backoff_base': self.backoff_base,
            'worker_poll_interval': self.worker_poll_interval,
            'default_timeout_seconds': self.default_timeout_seconds,
        }
