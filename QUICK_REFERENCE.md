# QueueCTL - Quick Reference Guide

## 🚀 Installation (30 seconds)

```bash
pip install -r requirements.txt
pip install -e .
queuectl --version
```

## 📝 Common Commands

### Enqueue Jobs

```bash
# Simple job
queuectl enqueue '{"id":"job1","command":"echo Hello"}'

# With custom retries
queuectl enqueue '{"id":"job2","command":"python script.py","max_retries":5}'

# Windows command
queuectl enqueue '{"id":"job3","command":"dir"}'

# Linux command
queuectl enqueue '{"id":"job4","command":"ls -la"}'
```

### Start Workers

```bash
# Single worker
queuectl worker start

# Multiple workers
queuectl worker start --count 3

# Stop: Press Ctrl+C
```

### Monitor Jobs

```bash
# Overall status
queuectl status

# List all jobs
queuectl list

# Filter by state
queuectl list --state pending
queuectl list --state completed
queuectl list --state failed
queuectl list --state dead

# Job details
queuectl info job1
```

### Manage DLQ

```bash
# View failed jobs
queuectl dlq list

# Retry a job
queuectl dlq retry job1
```

### Configuration

```bash
# Show config
queuectl config show

# Update settings
queuectl config set max-retries 5
queuectl config set backoff-base 3
queuectl config set worker-poll-interval 0.5
```

## 🎯 Quick Workflows

### Workflow 1: Process Simple Jobs

```bash
# 1. Enqueue
queuectl enqueue '{"id":"task1","command":"echo Task 1"}'
queuectl enqueue '{"id":"task2","command":"echo Task 2"}'

# 2. Check queue
queuectl status

# 3. Process
queuectl worker start

# 4. Verify (in another terminal)
queuectl list --state completed
```

### Workflow 2: Handle Failures

```bash
# 1. Enqueue job that will fail
queuectl enqueue '{"id":"fail1","command":"exit 1","max_retries":2}'

# 2. Start worker (will retry automatically)
queuectl worker start

# 3. After retries exhausted, check DLQ
queuectl dlq list

# 4. Fix and retry
queuectl dlq retry fail1
```

### Workflow 3: Batch Processing

```bash
# 1. Enqueue multiple jobs
for i in {1..10}; do
  queuectl enqueue "{\"id\":\"batch-$i\",\"command\":\"echo Processing $i\"}"
done

# 2. Process with multiple workers
queuectl worker start --count 5

# 3. Monitor progress
queuectl status
```

## 📊 Output Examples

### Status Output

```
==================================================
QueueCTL Status
==================================================

Job Statistics:
--------------------------------------------------
Total Jobs       15
Pending          3
Processing       1
Completed        10
Failed (Retrying) 1
Dead (DLQ)       0

Recent Jobs:
--------------------------------------------------
╒════════════╤═══════════╤═══════════╤═════════════════════╕
│ Job ID     │ State     │ Attempts  │ Created At          │
╞════════════╪═══════════╪═══════════╪═════════════════════╡
│ job1       │ completed │ 0/3       │ 2025-11-06 10:30:00 │
│ job2       │ processing│ 0/3       │ 2025-11-06 10:31:00 │
│ job3       │ pending   │ 0/3       │ 2025-11-06 10:32:00 │
╘════════════╧═══════════╧═══════════╧═════════════════════╛
```

### Job Info Output

```
Job Details:
==================================================
ID:              job-fail
Command:         exit 1
State:           dead
Attempts:        3/3
Created At:      2025-11-06 10:30:00
Updated At:      2025-11-06 10:35:15

Error Message:
--------------------------------------------------
Command exited with code 1
```

## 🧪 Testing

### Quick Test

```bash
# Windows
quick_test.bat

# Linux/Mac
./quick_test.sh
```

### Full Test Suite

```bash
python test_queuectl.py
```

### Interactive Demo

```bash
python demo.py
```

## ⚙️ Configuration Values

| Setting | Default | Description |
|---------|---------|-------------|
| max-retries | 3 | Maximum retry attempts |
| backoff-base | 2 | Exponential backoff base |
| worker-poll-interval | 1.0 | Polling interval (seconds) |

### Backoff Examples

With `backoff-base = 2`:
- Attempt 1: 2¹ = 2 seconds
- Attempt 2: 2² = 4 seconds
- Attempt 3: 2³ = 8 seconds

With `backoff-base = 3`:
- Attempt 1: 3¹ = 3 seconds
- Attempt 2: 3² = 9 seconds
- Attempt 3: 3³ = 27 seconds

## 🎨 Job States

```
┌─────────┐
│ PENDING │ ──────────────────┐
└────┬────┘                   │
     │                        │
     ▼                        │
┌────────────┐                │
│ PROCESSING │                │
└─────┬──────┘                │
      │                       │
      ├──► COMPLETED ✓        │
      │                       │
      └──► FAILED ────────────┤
              │                │
              │ (retry)        │
              └────────────────┘
              │
              │ (max retries)
              ▼
           DEAD (DLQ)
```

## 🔧 Troubleshooting

### Workers not processing

```bash
# Check pending jobs
queuectl list --state pending

# Restart workers
queuectl worker start
```

### Database locked

```bash
# Stop all workers (Ctrl+C)
# Delete database
del queuectl.db  # Windows
rm queuectl.db   # Linux/Mac
```

### Command not found

```bash
# Use direct method
python -m queuectl.cli status
```

## 📁 File Locations

- **Database**: `queuectl.db` (current directory)
- **Source**: `queuectl/` folder
- **Tests**: `test_queuectl.py`
- **Docs**: `*.md` files

## 🎯 Use Cases

### 1. Background Tasks
```bash
queuectl enqueue '{"id":"email1","command":"python send_email.py user@example.com"}'
```

### 2. Data Processing
```bash
queuectl enqueue '{"id":"process1","command":"python process_data.py input.csv"}'
```

### 3. Scheduled Jobs
```bash
# Enqueue now, process later
queuectl enqueue '{"id":"backup1","command":"python backup.py"}'
# Start workers when needed
queuectl worker start
```

### 4. Batch Operations
```bash
# Process multiple files
for file in *.txt; do
  queuectl enqueue "{\"id\":\"process-$file\",\"command\":\"python process.py $file\"}"
done
queuectl worker start --count 4
```

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| README.md | Main documentation |
| INSTALLATION.md | Setup guide |
| ARCHITECTURE.md | System design |
| QUICK_REFERENCE.md | This file |
| PROJECT_SUMMARY.md | Project overview |
| CHECKLIST.md | Feature checklist |
| GIT_SETUP.md | GitHub setup |

## 🔗 Help Commands

```bash
# General help
queuectl --help

# Command help
queuectl enqueue --help
queuectl worker --help
queuectl list --help
queuectl dlq --help
queuectl config --help
```

## 💡 Tips

1. **Always quote JSON** in commands
2. **Use Ctrl+C** to stop workers gracefully
3. **Check DLQ regularly** for failed jobs
4. **Monitor status** during processing
5. **Test commands** before enqueuing many jobs

## 🚨 Important Notes

- Job IDs must be unique
- Commands execute in shell
- Workers finish current job before stopping
- Database file must be accessible to all workers
- Configuration changes apply to new jobs

## ⌨️ Keyboard Shortcuts

- **Ctrl+C**: Stop workers gracefully
- **Ctrl+Z**: Suspend (not recommended)

## 📞 Getting Help

1. Check this quick reference
2. Read README.md
3. See INSTALLATION.md for setup issues
4. Review ARCHITECTURE.md for design details

---

**Quick Start**: `pip install -e . && queuectl status`

**Full Demo**: `python demo.py`

**Run Tests**: `python test_queuectl.py`
