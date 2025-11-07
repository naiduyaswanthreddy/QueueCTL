# QueueCTL Architecture

## System Design Overview

QueueCTL is a production-grade background job queue system built with Python and SQLite. This document provides an in-depth look at the system architecture, design decisions, and implementation details.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CLI Interface                        │
│                    (click-based)                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Queue Manager                          │
│  - Job Enqueuing                                        │
│  - Retry Logic                                          │
│  - DLQ Management                                       │
│  - Statistics                                           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Database Layer                         │
│  - SQLite Storage                                       │
│  - Thread-safe Operations                               │
│  - Transaction Management                               │
│  - Locking Mechanism                                    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   Worker Pool                            │
│  - Multiple Worker Threads                              │
│  - Job Execution                                        │
│  - Graceful Shutdown                                    │
│  - Retry Processing                                     │
└─────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Data Models (`models.py`)

#### Job Model
```python
@dataclass
class Job:
    id: str                          # Unique identifier
    command: str                     # Shell command to execute
    state: JobState                  # Current state
    attempts: int                    # Number of execution attempts
    max_retries: int                 # Maximum retry attempts
    created_at: datetime             # Creation timestamp
    updated_at: datetime             # Last update timestamp
    error_message: Optional[str]     # Last error message
    next_retry_at: Optional[datetime] # Next retry timestamp
    completed_at: Optional[datetime]  # Completion timestamp
```

#### Job States
- **PENDING**: Job is waiting to be processed
- **PROCESSING**: Job is currently being executed by a worker
- **COMPLETED**: Job executed successfully
- **FAILED**: Job failed but can be retried
- **DEAD**: Job permanently failed (in DLQ)

#### State Transitions
```
PENDING ──────────────────────────────────────► COMPLETED
   │                                                  ▲
   │                                                  │
   ▼                                                  │
PROCESSING ──────────────────────────────────────────┘
   │
   │ (on failure)
   ▼
FAILED ──────────────────────────────────────► PENDING
   │                                           (retry)
   │ (max retries exceeded)
   ▼
DEAD (DLQ)
```

### 2. Database Layer (`database.py`)

#### Schema Design

**Jobs Table:**
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT,
    next_retry_at TEXT,
    completed_at TEXT
);

CREATE INDEX idx_job_state ON jobs(state);
CREATE INDEX idx_next_retry ON jobs(next_retry_at);
```

**Config Table:**
```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

#### Thread Safety

Each thread gets its own database connection using thread-local storage:

```python
class Database:
    def __init__(self):
        self._local = threading.local()
    
    def _get_connection(self):
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(...)
        return self._local.connection
```

#### Locking Mechanism

To prevent race conditions, we use SQLite's `BEGIN IMMEDIATE` transaction:

```python
@contextmanager
def _get_cursor(self):
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")  # Exclusive lock
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

This ensures that:
1. Only one transaction can modify data at a time
2. No two workers can pick up the same job
3. State transitions are atomic

### 3. Queue Manager (`queue_manager.py`)

#### Job Execution Flow

```
1. Worker calls get_next_job()
2. Database atomically moves job from PENDING → PROCESSING
3. Worker executes command via subprocess
4. On success: PROCESSING → COMPLETED
5. On failure: PROCESSING → FAILED (with retry) or DEAD (if max retries)
```

#### Retry Logic

```python
def _handle_job_failure(self, job, error_message):
    job.attempts += 1
    
    if job.attempts >= job.max_retries:
        # Move to DLQ
        job.state = JobState.DEAD
    else:
        # Schedule retry with exponential backoff
        delay = backoff_base ** job.attempts
        job.next_retry_at = now + timedelta(seconds=delay)
        job.state = JobState.FAILED
```

#### Exponential Backoff

Formula: `delay = base ^ attempts`

Example with `base = 2`:
- Attempt 1: 2¹ = 2 seconds
- Attempt 2: 2² = 4 seconds
- Attempt 3: 2³ = 8 seconds
- Attempt 4: 2⁴ = 16 seconds

This prevents overwhelming failing services while allowing quick recovery.

### 4. Worker Implementation (`worker.py`)

#### Worker Loop

```python
def run(self):
    while not stop_event.is_set():
        # Process retries first
        queue_manager.process_retries()
        
        # Get next job (with locking)
        job = queue_manager.get_next_job()
        
        if job:
            # Execute job
            queue_manager.execute_job(job)
        else:
            # No jobs, sleep
            time.sleep(poll_interval)
```

#### Graceful Shutdown

```python
# Signal handler
signal.signal(signal.SIGINT, self._signal_handler)

def _signal_handler(self, signum, frame):
    # Set stop event
    self.stop_event.set()
    
    # Wait for workers to finish current jobs
    for thread in self.workers:
        thread.join(timeout=30)
```

Benefits:
- No partial job execution
- Clean state in database
- No orphaned jobs

#### Multi-Worker Concurrency

```
Worker 1: [Job A] ──► [Job D] ──► [Job G]
Worker 2: [Job B] ──► [Job E] ──► [Job H]
Worker 3: [Job C] ──► [Job F] ──► [Job I]
```

Each worker:
1. Has its own database connection
2. Polls for jobs independently
3. Uses database locking to prevent conflicts
4. Processes jobs in parallel

### 5. CLI Interface (`cli.py`)

Built with Click framework for:
- Subcommands and command groups
- Type validation
- Help text generation
- Error handling

#### Command Structure

```
queuectl
├── enqueue <job_json>
├── worker
│   ├── start [--count N]
│   └── stop
├── status
├── list [--state STATE]
├── info <job_id>
├── dlq
│   ├── list
│   └── retry <job_id>
└── config
    ├── show
    └── set <key> <value>
```

## Concurrency & Race Conditions

### Problem: Duplicate Job Processing

Without proper locking, two workers could pick up the same job:

```
Time  Worker 1              Worker 2
----  ------------------    ------------------
T1    SELECT job1 (PENDING)
T2                          SELECT job1 (PENDING)
T3    UPDATE job1 → PROCESSING
T4                          UPDATE job1 → PROCESSING
T5    Execute job1          Execute job1 (DUPLICATE!)
```

### Solution: Atomic State Transition

```python
def get_pending_job(self):
    with self._get_cursor() as cursor:
        # Get job
        cursor.execute("SELECT * FROM jobs WHERE state = ? LIMIT 1", 
                      (JobState.PENDING.value,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Atomically update state
        cursor.execute("""
            UPDATE jobs 
            SET state = ?, updated_at = ?
            WHERE id = ? AND state = ?
        """, (JobState.PROCESSING.value, now, job_id, JobState.PENDING.value))
        
        # Check if update was successful
        if cursor.rowcount == 0:
            return None  # Another worker got it
        
        return job
```

The `WHERE state = ?` clause ensures only one worker can successfully update the job.

## Performance Considerations

### Database Indexes

```sql
-- Fast lookup by state
CREATE INDEX idx_job_state ON jobs(state);

-- Fast lookup for retry processing
CREATE INDEX idx_next_retry ON jobs(next_retry_at);
```

### Connection Pooling

Each worker thread maintains its own connection to avoid:
- Connection contention
- Lock wait timeouts
- Performance bottlenecks

### Polling Interval

Configurable `worker_poll_interval` balances:
- **Lower value**: Faster job pickup, higher CPU usage
- **Higher value**: Lower CPU usage, slower job pickup

Default: 1.0 second (good balance)

## Error Handling

### Command Execution Errors

```python
try:
    result = subprocess.run(command, shell=True, timeout=300)
    if result.returncode == 0:
        # Success
    else:
        # Failure - retry
except subprocess.TimeoutExpired:
    # Timeout - retry
except FileNotFoundError:
    # Command not found - retry
except Exception as e:
    # Other error - retry
```

### Database Errors

All database operations use transactions:
```python
try:
    cursor.execute("BEGIN IMMEDIATE")
    # ... operations ...
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

## Scalability

### Current Limitations

1. **Single Machine**: SQLite is not distributed
2. **Thread-based**: Python GIL limits CPU parallelism
3. **File-based Storage**: Not suitable for millions of jobs

### Scaling Options

#### Vertical Scaling (Single Machine)
- ✅ Increase worker count (tested up to 10 workers)
- ✅ Use SSD for faster I/O
- ✅ Optimize polling interval

#### Horizontal Scaling (Multiple Machines)
Would require:
- Replace SQLite with PostgreSQL/MySQL
- Implement distributed locking (Redis)
- Add worker registration/heartbeat
- Load balancer for job distribution

## Testing Strategy

### Unit Tests
- Job state transitions
- Retry logic
- Exponential backoff calculation
- Database operations

### Integration Tests
- End-to-end job execution
- Multi-worker concurrency
- Graceful shutdown
- Persistence across restarts

### Test Coverage
1. ✅ Success path
2. ✅ Failure and retry
3. ✅ DLQ movement
4. ✅ Concurrency
5. ✅ Persistence
6. ✅ Invalid commands
7. ✅ Configuration

## Security Considerations

### Command Injection

Jobs execute shell commands, which could be dangerous:

**Mitigation:**
- Jobs are explicitly enqueued (not user input)
- Consider adding command whitelist for production
- Run workers with limited permissions

### Database Security

- SQLite file should have restricted permissions
- No SQL injection (parameterized queries used)
- Transactions prevent data corruption

## Monitoring & Observability

### Current Capabilities

```bash
# Real-time status
queuectl status

# Job history
queuectl list

# Individual job details
queuectl info <job-id>

# DLQ monitoring
queuectl dlq list
```

### Future Enhancements

- Prometheus metrics export
- Structured logging (JSON)
- Performance metrics (job duration, throughput)
- Alerting on DLQ threshold

## Deployment

### Production Checklist

- [ ] Set appropriate `max_retries` for your use case
- [ ] Configure `backoff_base` based on service characteristics
- [ ] Set `worker_poll_interval` for desired responsiveness
- [ ] Monitor DLQ regularly
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Run workers as system service
- [ ] Set resource limits (CPU, memory)

### System Service Example (Linux)

```ini
[Unit]
Description=QueueCTL Worker
After=network.target

[Service]
Type=simple
User=queuectl
WorkingDirectory=/opt/queuectl
ExecStart=/opt/queuectl/venv/bin/queuectl worker start --count 3
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Conclusion

QueueCTL provides a robust, production-ready job queue system with:
- ✅ Reliable job execution
- ✅ Automatic retry with backoff
- ✅ Concurrency control
- ✅ Persistent storage
- ✅ Clean CLI interface

The architecture is designed for:
- **Simplicity**: Easy to understand and maintain
- **Reliability**: ACID transactions, atomic operations
- **Scalability**: Multi-worker support, efficient indexing
- **Observability**: Comprehensive status and monitoring

For most single-machine use cases, this design provides excellent performance and reliability.
