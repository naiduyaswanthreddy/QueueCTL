#!/bin/bash

# Quick test script for QueueCTL (POSIX)

set -euo pipefail

DB_FILE="queuectl_quicktest.db"

echo "========================================"
echo "QueueCTL Quick Test"
echo "========================================"

# Clean up
rm -f "$DB_FILE"

echo ""
echo "[1] Enqueuing test jobs..."
python -m queuectl.cli enqueue '{"id":"job1","command":"echo Hello from Job 1"}' --db "$DB_FILE"
python -m queuectl.cli enqueue '{"id":"job2","command":"sleep 2"}' --db "$DB_FILE"
python -m queuectl.cli enqueue '{"id":"job3","command":"echo Job 3 completed"}' --db "$DB_FILE"

echo ""
echo "[2] Checking status..."
python -m queuectl.cli status --db "$DB_FILE"

echo ""
echo "[3] Listing pending jobs..."
python -m queuectl.cli list --state pending --db "$DB_FILE"

echo ""
echo "[4] Showing configuration..."
python -m queuectl.cli config show --db "$DB_FILE"

echo ""
echo "========================================"
echo "Test setup complete!"
echo ""
echo "To process jobs, run:"
echo "  python -m queuectl.cli worker start --count 2 --db $DB_FILE"
echo ""
echo "Press Ctrl+C to stop workers when done."
echo "========================================"
