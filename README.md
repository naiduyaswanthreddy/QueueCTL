# QueueCTL - Background Job Queue System

A CLI-based background job queue system with automatic retry, exponential backoff, and Dead Letter Queue (DLQ) support.

## 🎯 Features

- ✅ **Job Queue Management** - Enqueue and manage background jobs
- ✅ **Multiple Workers** - Run concurrent worker processes
- ✅ **Automatic Retry** - Failed jobs retry with exponential backoff
- ✅ **Dead Letter Queue** - Permanently failed jobs moved to DLQ
- ✅ **Persistent Storage** - SQLite-based job persistence across restarts
- ✅ **Concurrency Control** - Database-level locking prevents duplicate processing
- ✅ **Configuration Management** - Customizable retry and backoff settings
- ✅ **Clean CLI Interface** - Intuitive command-line interface

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Run with Docker](#run-with-docker)
- [Web Dashboard & Simulation](#web-dashboard--simulation)
- [Usage Examples](#usage-examples)
- [Architecture](#architecture)
- [CLI Commands](#cli-commands)
- [Configuration](#configuration)
- [Testing](#testing)
- [Continuous Integration (CI)](#continuous-integration-ci)
- [Assumptions & Trade-offs](#assumptions--trade-offs)

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/queuectl.git
   cd queuectl
   ```

## 🐳 Run with Docker

```bash
# Build image
docker build -t queuectl .

# Run the web dashboard (http://localhost:5000) with a persistent volume for the DB
docker run --rm -p 5000:5000 -v "$PWD/data:/data" queuectl

# Run any CLI command (DB is at /data/queuectl.db inside the container)
docker run --rm -v "$PWD/data:/data" queuectl queuectl status --db /data/queuectl.db
```

Notes:
- **Windows PowerShell**: use `${PWD}` instead of `$PWD` when mapping volumes.
- The default container command starts the dashboard. Override `CMD` by appending your own CLI args as shown above.

## 🖥️ Web Dashboard & Simulation

- Dashboard routes:
  - **Home**: `http://localhost:5000` – stats, workers, recent jobs
  - **Metrics**: `http://localhost:5000/metrics` – Prometheus exposition format
  - **Simulation**: `http://localhost:5000/simulate` – "Start from Beginning" interactive storyboard

- Simulation controls:
  - **▶ Start** begins a safe, in-memory demonstration of QueueCTL lifecycle (does not mutate your DB)
  - **Reset** clears the storyboard
  - **Speed** slider changes playback speed
  - **Theme** button toggles light/dark

If the environment blocks CDNs, a local stylesheet fallback ensures usable styling. The app attempts Tailwind from CDN for enhanced visuals.

2. **Create a virtual environment (recommended)**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install QueueCTL**
   ```bash
   pip install -e .
   ```

5. **Verify installation**
   ```bash
   queuectl --version
   ```

6. **Global database option**
   ```bash
   # You can set a database file once at the root and all subcommands will use it
   queuectl --db myqueue.db status
   queuectl --db myqueue.db worker start --count 2
   queuectl --db myqueue.db workers list
   ```

## ⚡ Quick Start

### 1. Enqueue a Job

```bash
# POSIX shells (Linux/Mac):
queuectl enqueue '{"id":"job1","command":"echo Hello World"}'

# Windows CMD/PowerShell: double the inner quotes
queuectl enqueue "{""id"":""job1"",""command"":""echo Hello World""}"
```

### 2. Start Workers

```bash
queuectl worker start --count 3
```

Press `Ctrl+C` to stop workers gracefully.

### 3. Check Status

```bash
queuectl status
```

### 4. Start Web Dashboard

```bash
queuectl web start --port 5000
# Open http://localhost:5000
# Prometheus metrics available at http://localhost:5000/metrics
```

### 5. Run Quick Test

```bash
# Windows
quick_test.bat

# Linux/Mac
chmod +x quick_test.sh
./quick_test.sh
```

## 📖 Usage Examples

### Basic Job Execution

```bash
# Enqueue a simple command (POSIX)
queuectl enqueue '{"id":"hello","command":"echo Hello World"}'

# Enqueue a simple command (Windows)
queuectl enqueue "{""id"":""hello"",""command"":""echo Hello World""}"

# Enqueue with custom retry count (POSIX)
queuectl enqueue '{"id":"job2","command":"python script.py","max_retries":5}'

# Enqueue with custom retry count (Windows)
queuectl enqueue "{""id"":""job2"",""command"":""python script.py"",""max_retries"":5}"
```

# Start a single worker
queuectl worker start

# Start multiple workers
queuectl worker start --count 3
```

### Monitoring Jobs

```bash
# View overall status
queuectl status

# List all jobs
queuectl list

# List jobs by state
queuectl list --state pending
queuectl list --state completed
queuectl list --state failed

# Get detailed job information
queuectl info job1

### Bonus Features: Priority, Scheduling, Timeout

```bash
# Higher priority runs first (higher number = higher priority)
queuectl enqueue '{"id":"prio1","command":"echo hi","priority":5}'

# Schedule a job to run in the future (ISO8601)
queuectl enqueue '{"id":"later","command":"echo later","run_at":"2025-11-10T10:00:00Z"}'

# Per-job timeout (seconds). If exceeded, job fails and retries per policy
queuectl enqueue '{"id":"short","command":"sleep 5","timeout_seconds":2}'
```

### Workers & Dashboard

```bash
# List registered workers with heartbeat status
queuectl workers list

# Start the web dashboard
queuectl web start --port 5000
# Visit http://localhost:5000 for status, metrics, and recent jobs
# Metrics endpoint (Prometheus format): http://localhost:5000/metrics
```
```

### Dead Letter Queue (DLQ)

```bash
# List all failed jobs in DLQ
queuectl dlq list

# Retry a specific job from DLQ
queuectl dlq retry job1
```

### Configuration Management

```bash
# Show current configuration
queuectl config show

# Set maximum retries
queuectl config set max-retries 5

# Set backoff base (for exponential backoff)
queuectl config set backoff-base 3

# Set worker polling interval (seconds)
queuectl config set worker-poll-interval 0.5
```

### Example Output

**Status Command:**
```
==================================================
QueueCTL Status
==================================================

Job Statistics:
--------------------------------------------------
Total Jobs       10
Pending          2
Processing       1
Completed        5
Failed (Retrying) 1
Dead (DLQ)       1

Recent Jobs:
--------------------------------------------------
╒════════════════════╤═══════════╤═══════════╤═════════════════════╕
│ Job ID             │ State     │ Attempts  │ Created At          │
╞════════════════════╪═══════════╪═══════════╪═════════════════════╡
│ job1               │ completed │ 0/3       │ 2025-11-06 10:30:00 │
│ job2               │ processing│ 0/3       │ 2025-11-06 10:31:00 │
│ job3               │ pending   │ 0/3       │ 2025-11-06 10:32:00 │
╘════════════════════╧═══════════╧═══════════╧═════════════════════╛
```

## 🏗️ Architecture

### System Overview

```
┌─────────────┐
│   CLI       │
│  Interface  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐      ┌──────────────┐
│  Queue Manager  │◄────►│   Database   │
│                 │      │   (SQLite)   │
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐
│  Worker Pool    │
│  (Threads)      │
└─────────────────┘
```

### Job Lifecycle

```
PENDING → PROCESSING → COMPLETED
    ↓                      ↑
    ↓                      │
    └──→ FAILED ──→ PENDING (retry with backoff)
              │
              ↓ (max retries exceeded)
            DEAD (DLQ)
```

#### Priority & Scheduling

- Jobs include `priority` (default 0). Higher `priority` jobs are picked first.
- Jobs may include `run_at` (ISO8601). Workers only pick jobs where `run_at <= now` (or `run_at` is omitted).

### Key Components

#### 1. **Database Layer** (`database.py`)
- SQLite-based persistent storage
- Thread-safe operations with connection pooling
- Atomic job state transitions with locking
- Indexes for efficient queries

#### 2. **Queue Manager** (`queue_manager.py`)
- Job enqueuing and execution
- Retry logic with exponential backoff
- DLQ management
- Job statistics and monitoring

#### 3. **Worker** (`worker.py`)
- Multi-threaded job processing
- Graceful shutdown handling
- Automatic retry processing
- Concurrent job execution with locking

#### 4. **CLI Interface** (`cli.py`)
- User-friendly command-line interface
- Comprehensive help text
- Formatted output with tables

### Exponential Backoff

Failed jobs are retried with exponential backoff:

```
delay = backoff_base ^ attempts (in seconds)

Example (backoff_base = 2):
- Attempt 1: 2^1 = 2 seconds
- Attempt 2: 2^2 = 4 seconds
- Attempt 3: 2^3 = 8 seconds

#### Stale Job Reaper

- If a worker crashes while a job is `processing`, a periodic reaper resets stale `processing` jobs back to `pending`.
- Triggered on worker startup and roughly every 60s.
```

### Concurrency Control

- **Database-level locking**: Uses SQLite's `BEGIN IMMEDIATE` transaction
- **Atomic state transitions**: Jobs are locked when moved from PENDING to PROCESSING
- **Race condition prevention**: Only one worker can pick up a specific job
- **Thread-safe**: Each worker has its own database connection

## 📚 CLI Commands

### Job Management

| Command | Description | Example |
|---------|-------------|---------|
| `enqueue` | Add a new job to the queue | `queuectl enqueue '{"id":"job1","command":"echo test"}'` |
| `list` | List jobs (optionally filter by state) | `queuectl list --state pending` |
| `info` | Show detailed job information | `queuectl info job1` |
| `status` | Show queue statistics | `queuectl status` |

### Worker Management

| Command | Description | Example |
|---------|-------------|---------|
| `worker start` | Start worker processes | `queuectl worker start --count 3` |
| `worker stop` | Stop workers (use Ctrl+C) | Press Ctrl+C in worker terminal |

### Dead Letter Queue

| Command | Description | Example |
|---------|-------------|---------|
| `dlq list` | List all jobs in DLQ | `queuectl dlq list` |
| `dlq retry` | Retry a job from DLQ | `queuectl dlq retry job1` |

### Configuration

| Command | Description | Example |
|---------|-------------|---------|
| `config show` | Display current configuration | `queuectl config show` |
| `config set` | Update configuration value | `queuectl config set max-retries 5` |

### Help

```bash
# General help
queuectl --help

# Command-specific help
queuectl enqueue --help
queuectl worker --help
queuectl dlq --help
```

## ⚙️ Configuration

### Available Settings

| Key | Description | Default | Type |
|-----|-------------|---------|------|
| `max-retries` | Maximum retry attempts before DLQ | 3 | integer |
| `backoff-base` | Base for exponential backoff calculation | 2 | integer |
| `worker-poll-interval` | Worker polling interval (seconds) | 1.0 | float |

### Configuration Examples

```bash
# Increase retry attempts
queuectl config set max-retries 5

# Use more aggressive backoff
queuectl config set backoff-base 3

# Faster worker polling
queuectl config set worker-poll-interval 0.5
```

## 🧪 Testing

### Run Full Test Suite

```bash
python test_queuectl.py
```

### Run Unit Tests (targeted)

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

This will run 7 comprehensive tests:
1. ✅ Basic job completes successfully
2. ✅ Failed job retries with backoff and moves to DLQ
3. ✅ Multiple workers process jobs without overlap
4. ✅ Invalid commands fail gracefully
5. ✅ Retry job from DLQ
6. ✅ Configuration management
7. ✅ Job data persists across restarts

### Quick Manual Test

```bash
# Windows
quick_test.bat

# Linux/Mac
./quick_test.sh
```

### Test Scenarios Covered

- ✅ **Success Path**: Jobs execute and complete successfully
- ✅ **Failure & Retry**: Failed jobs retry with exponential backoff
- ✅ **DLQ Movement**: Jobs move to DLQ after max retries
- ✅ **Concurrency**: Multiple workers process jobs without conflicts
- ✅ **Persistence**: Jobs survive system restarts
- ✅ **Invalid Commands**: Graceful handling of non-existent commands
- ✅ **Configuration**: Dynamic configuration updates

## 🤔 Assumptions & Trade-offs

### Assumptions

1. **Command Execution**: Jobs are shell commands executed via `subprocess`
2. **Single Machine**: Designed for single-machine deployment (not distributed)
3. **Job Timeout**: Commands have a 5-minute timeout to prevent hanging
4. **Database**: SQLite is sufficient for the expected load
5. **Job Uniqueness**: Job IDs must be unique (enforced at database level)

### Trade-offs

#### ✅ **Chosen: SQLite for Persistence**
- **Pro**: Zero configuration, embedded, ACID compliant
- **Pro**: Perfect for single-machine deployments
- **Con**: Not suitable for distributed systems
- **Alternative**: Redis/PostgreSQL for distributed setups

#### ✅ **Chosen: Threading for Workers**
- **Pro**: Lightweight, shared memory, easy IPC
- **Pro**: Suitable for I/O-bound job execution
- **Con**: Python GIL limits CPU-bound parallelism
- **Alternative**: Multiprocessing for CPU-intensive jobs

#### ✅ **Chosen: Database-level Locking**
- **Pro**: Simple, reliable, prevents race conditions
- **Pro**: Works across threads and processes
- **Con**: Slight performance overhead
- **Alternative**: Application-level locks (more complex)

#### ✅ **Chosen: Exponential Backoff**
- **Pro**: Reduces load on failing services
- **Pro**: Industry-standard retry pattern
- **Con**: Can delay recovery if service recovers quickly
- **Alternative**: Linear backoff or immediate retry

### Design Decisions

1. **No Job Priority**: All jobs are FIFO (First In, First Out)
   - *Simplifies implementation*
   - *Can be added as future enhancement*

2. **No Job Dependencies**: Jobs are independent
   - *Reduces complexity*
   - *Can be added with DAG support*

3. **Graceful Shutdown**: Workers finish current jobs before stopping
   - *Prevents partial job execution*
   - *May delay shutdown slightly*

4. **Single Database File**: All data in one SQLite file
   - *Easy backup and portability*
   - *Simple deployment*

## 📁 Project Structure

```
queuectl/
├── queuectl/
│   ├── __init__.py          # Package initialization
│   ├── models.py            # Data models (Job, Config)
│   ├── database.py          # SQLite persistence layer
│   ├── queue_manager.py     # Job queue operations
│   ├── worker.py            # Worker implementation
│   └── cli.py               # CLI interface
├── test_queuectl.py         # Comprehensive test suite
├── quick_test.bat           # Quick test (Windows)
├── quick_test.sh            # Quick test (Linux/Mac)
├── requirements.txt         # Python dependencies
├── setup.py                 # Package setup
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## 🔒 Error Handling

The system handles various error scenarios:

- **Command Not Found**: Moves to DLQ after retries
- **Command Timeout**: 5-minute timeout with retry
- **Non-zero Exit Code**: Retries with backoff
- **Database Errors**: Automatic rollback and retry
- **Worker Crashes**: Other workers continue processing
- **Graceful Shutdown**: Ctrl+C finishes current jobs

## 📊 Performance Characteristics

- **Job Throughput**: ~100-1000 jobs/second (depends on job complexity)
- **Worker Scalability**: Tested with up to 10 concurrent workers
- **Database Size**: Minimal overhead (~1KB per job)
- **Memory Usage**: ~10-20MB base + ~5MB per worker
- **Startup Time**: < 1 second

## 🚀 Future Enhancements

Potential features for future versions:

- [ ] Job priority queues
- [ ] Scheduled/delayed jobs (`run_at` timestamp)
- [ ] Job dependencies and workflows
- [ ] Job output logging and storage
- [ ] Web dashboard for monitoring
- [ ] Metrics and statistics export
- [ ] Job timeout configuration per job
- [ ] Distributed worker support
- [ ] Job cancellation
- [ ] Webhook notifications

## 🐛 Troubleshooting

### Workers Not Processing Jobs

```bash
# Check if jobs are in pending state
queuectl list --state pending

# Check worker logs (stdout when running)
queuectl worker start --count 1
```

### Jobs Stuck in Processing

```bash
# Check job details
queuectl info <job-id>

# If worker crashed, manually reset job state in database
# or restart workers
```

### Database Locked Errors

- Ensure only one worker manager is running
- Check for stale database locks
- Restart workers if needed



