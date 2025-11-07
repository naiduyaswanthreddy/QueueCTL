# QueueCTL - Installation & Setup Guide

## Quick Installation

### Step 1: Prerequisites

Ensure you have Python 3.8 or higher installed:

```bash
python --version
# Should show Python 3.8.x or higher
```

### Step 2: Clone or Download

If you have the repository:
```bash
cd Flam_QueueCTL
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `click` - CLI framework
- `tabulate` - Table formatting

### Step 4: Install QueueCTL

```bash
pip install -e .
```

This installs QueueCTL in editable mode, making the `queuectl` command available globally.

### Step 5: Verify Installation

```bash
queuectl --version
```

You should see: `queuectl, version 1.0.0`

## Alternative: Run Without Installation

If you prefer not to install globally, you can run QueueCTL directly:

```bash
# Instead of: queuectl <command>
# Use: python -m queuectl.cli <command>

python -m queuectl.cli --version
python -m queuectl.cli status
```

## Quick Test

Run the quick test to verify everything works:

### Windows:
```bash
quick_test.bat
```

### Linux/Mac:
```bash
chmod +x quick_test.sh
./quick_test.sh
```

## First Steps

### 1. Check Configuration
```bash
queuectl config show
```

### 2. Enqueue Your First Job
```bash
queuectl enqueue "{\"id\":\"test1\",\"command\":\"echo Hello QueueCTL\"}"
```

### 3. Check Status
```bash
queuectl status
```

### 4. Start a Worker
```bash
queuectl worker start
```

Press `Ctrl+C` to stop the worker.

## Running the Demo

For a comprehensive demonstration:

```bash
python demo.py
```

This will showcase all features of QueueCTL.

## Running Tests

To run the full test suite:

```bash
python test_queuectl.py
```

## Troubleshooting

### Issue: `queuectl: command not found`

**Solution 1**: Ensure pip install location is in PATH
```bash
# Windows
pip show queuectl
# Check the Location and ensure it's in your PATH
```

**Solution 2**: Use the direct method
```bash
python -m queuectl.cli <command>
```

### Issue: `ModuleNotFoundError: No module named 'click'`

**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### Issue: `Permission denied` on Linux/Mac

**Solution**: Make scripts executable
```bash
chmod +x quick_test.sh
```

### Issue: Database locked errors

**Solution**: Ensure only one worker manager is running
```bash
# Stop all workers (Ctrl+C)
# Delete database if needed
rm queuectl.db  # Linux/Mac
del queuectl.db  # Windows
```

## Uninstallation

```bash
pip uninstall queuectl
```

## Development Setup

For development work:

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   
   # Activate
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

2. **Install in editable mode**:
   ```bash
   pip install -e .
   ```

3. **Make changes** to the code

4. **Test changes**:
   ```bash
   python test_queuectl.py
   ```

## Configuration Files

QueueCTL creates the following files:

- `queuectl.db` - SQLite database (stores jobs and config)
- No other files are created

## Database Location

By default, `queuectl.db` is created in the current working directory.

To use a different location, use the `--db` flag:

```bash
queuectl --db /path/to/database.db status
queuectl --db /path/to/database.db worker start
```

## System Service Setup (Optional)

### Linux (systemd)

Create `/etc/systemd/system/queuectl.service`:

```ini
[Unit]
Description=QueueCTL Worker
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/queuectl
ExecStart=/path/to/venv/bin/queuectl worker start --count 3
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable queuectl
sudo systemctl start queuectl
sudo systemctl status queuectl
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., At startup)
4. Set action: Start a program
   - Program: `C:\path\to\python.exe`
   - Arguments: `-m queuectl.cli worker start --count 3`
   - Start in: `C:\path\to\queuectl`

## Next Steps

- Read the [README.md](README.md) for usage examples
- Check [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Review [CHECKLIST.md](CHECKLIST.md) for feature completeness

## Support

For issues or questions, please check the README.md troubleshooting section.

---

**Happy Queueing! 🚀**
