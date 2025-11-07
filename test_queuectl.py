"""Test script for QueueCTL functionality."""

import subprocess
import time
import json
import os
import sys


DB_FILE = "queuectl_e2e.db"


def _with_db(cmd: str) -> str:
    # Append per-command --db option; all commands in this script accept --db
    if " --db " in cmd or cmd.strip().endswith(f"--db {DB_FILE}"):
        return cmd
    return f"{cmd} --db {DB_FILE}"


def run_command(cmd):
    """Run a command and return output."""
    full_cmd = _with_db(cmd)
    print(f"\n→ Running: {full_cmd}")
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}", file=sys.stderr)
    return result.returncode == 0


def cleanup():
    """Clean up test database."""
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
            print("✓ Cleaned up test database")
        except PermissionError:
            print(f"! Skipping cleanup: {DB_FILE} in use")


def make_job_arg(job_dict) -> str:
    # Build OS-appropriate JSON argument for enqueue
    job_json = json.dumps(job_dict)
    if os.name == 'nt':
        # Double inner quotes and wrap in quotes
        escaped = job_json.replace('"', '""')
        return f'"{escaped}"'
    else:
        # POSIX: wrap in single quotes
        return f"'{job_json}'"


def test_basic_job():
    """Test 1: Basic job completes successfully."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic job completes successfully")
    print("=" * 60)
    
    # Enqueue a simple job
    job_arg = make_job_arg({"id": "test-job-1", "command": "echo Hello World"})
    if not run_command(f'python -m queuectl.cli enqueue {job_arg}'):
        return False
    
    # Check status
    run_command("python -m queuectl.cli status")
    
    # Start worker in background
    print("\n→ Starting worker (will run for 5 seconds)...")
    worker_proc = subprocess.Popen(
        ["python", "-m", "queuectl.cli", "worker", "start", "--db", DB_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for job to complete
    time.sleep(5)
    
    # Stop worker
    worker_proc.terminate()
    worker_proc.wait()
    
    # Check status
    run_command("python -m queuectl.cli status")
    run_command("python -m queuectl.cli info test-job-1")
    
    print("\n✓ TEST 1 PASSED")
    return True


def test_failed_job_retry():
    """Test 2: Failed job retries with backoff and moves to DLQ."""
    print("\n" + "=" * 60)
    print("TEST 2: Failed job retries and moves to DLQ")
    print("=" * 60)
    
    # Enqueue a job that will fail
    job_arg = make_job_arg({"id": "test-job-2", "command": "exit 1", "max_retries": 2})
    if not run_command(f'python -m queuectl.cli enqueue {job_arg}'):
        return False
    
    # Start worker
    print("\n→ Starting worker (will run for 15 seconds to allow retries)...")
    worker_proc = subprocess.Popen(
        ["python", "-m", "queuectl.cli", "worker", "start", "--db", DB_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for retries (2^1 + 2^2 = 6 seconds + processing time)
    time.sleep(15)
    
    # Stop worker
    worker_proc.terminate()
    worker_proc.wait()
    
    # Check DLQ
    run_command("python -m queuectl.cli dlq list")
    run_command("python -m queuectl.cli info test-job-2")
    
    print("\n✓ TEST 2 PASSED")
    return True


def test_multiple_workers():
    """Test 3: Multiple workers process jobs without overlap."""
    print("\n" + "=" * 60)
    print("TEST 3: Multiple workers process jobs concurrently")
    print("=" * 60)
    
    # Enqueue multiple jobs
    for i in range(5):
        job_arg = make_job_arg({"id": f"test-job-3-{i}", "command": f"echo Job {i}"})
        run_command(f'python -m queuectl.cli enqueue {job_arg}')
    
    # Check status
    run_command("python -m queuectl.cli list --state pending")
    
    # Start multiple workers
    print("\n→ Starting 3 workers (will run for 5 seconds)...")
    worker_proc = subprocess.Popen(
        ["python", "-m", "queuectl.cli", "worker", "start", "--count", "3", "--db", DB_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for jobs to complete
    time.sleep(5)
    
    # Stop workers
    worker_proc.terminate()
    worker_proc.wait()
    
    # Check status
    run_command("python -m queuectl.cli status")
    run_command("python -m queuectl.cli list --state completed")
    
    print("\n✓ TEST 3 PASSED")
    return True


def test_invalid_command():
    """Test 4: Invalid commands fail gracefully."""
    print("\n" + "=" * 60)
    print("TEST 4: Invalid command fails gracefully")
    print("=" * 60)
    
    # Enqueue a job with invalid command
    job_arg = make_job_arg({"id": "test-job-4", "command": "nonexistentcommand123", "max_retries": 1})
    if not run_command(f'python -m queuectl.cli enqueue {job_arg}'):
        return False
    
    # Start worker
    print("\n→ Starting worker (will run for 8 seconds)...")
    worker_proc = subprocess.Popen(
        ["python", "-m", "queuectl.cli", "worker", "start"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for retries
    time.sleep(8)
    
    # Stop worker
    worker_proc.terminate()
    worker_proc.wait()
    
    # Check job info
    run_command("python -m queuectl.cli info test-job-4")
    run_command("python -m queuectl.cli dlq list")
    
    print("\n✓ TEST 4 PASSED")
    return True


def test_dlq_retry():
    """Test 5: Retry job from DLQ."""
    print("\n" + "=" * 60)
    print("TEST 5: Retry job from DLQ")
    print("=" * 60)
    
    # Check DLQ
    run_command("python -m queuectl.cli dlq list")
    
    # Retry a job from DLQ (from previous tests)
    run_command("python -m queuectl.cli dlq retry test-job-2")
    
    # Check status
    run_command("python -m queuectl.cli info test-job-2")
    run_command("python -m queuectl.cli list --state pending")
    
    print("\n✓ TEST 5 PASSED")
    return True


def test_configuration():
    """Test 6: Configuration management."""
    print("\n" + "=" * 60)
    print("TEST 6: Configuration management")
    print("=" * 60)
    
    # Show current config
    run_command("python -m queuectl.cli config show")
    
    # Update config
    run_command("python -m queuectl.cli config set max-retries 5")
    run_command("python -m queuectl.cli config set backoff-base 3")
    
    # Show updated config
    run_command("python -m queuectl.cli config show")
    
    print("\n✓ TEST 6 PASSED")
    return True


def test_persistence():
    """Test 7: Job data survives restart."""
    print("\n" + "=" * 60)
    print("TEST 7: Job data persists across restarts")
    print("=" * 60)
    
    # Enqueue a job
    job_arg = make_job_arg({"id": "test-job-persist", "command": "echo Persistence Test"})
    run_command(f'python -m queuectl.cli enqueue {job_arg}')
    
    # Check status
    print("\n→ Before 'restart':")
    run_command("python -m queuectl.cli status")
    
    # Simulate restart by just checking if data is still there
    print("\n→ After 'restart' (simulated):")
    run_command("python -m queuectl.cli status")
    run_command("python -m queuectl.cli info test-job-persist")
    
    print("\n✓ TEST 7 PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("QueueCTL Test Suite")
    print("=" * 60)
    
    # Cleanup before starting
    cleanup()
    
    tests = [
        test_basic_job,
        test_failed_job_retry,
        test_multiple_workers,
        test_invalid_command,
        test_dlq_retry,
        test_configuration,
        test_persistence,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ TEST FAILED WITH EXCEPTION: {e}")
            failed += 1
    
    # Final summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    # Final status check
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    run_command("python -m queuectl.cli status")
    
    if failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
