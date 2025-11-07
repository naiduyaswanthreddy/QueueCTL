"""
Interactive demo script for QueueCTL.
This script demonstrates all major features of the system.
"""

import subprocess
import time
import json
import os
import sys


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_step(step_num, text):
    """Print a step number and description."""
    print(f"\n[Step {step_num}] {text}")
    print("-" * 70)


def run_cmd(cmd, wait=True):
    """Run a command and optionally wait."""
    print(f"$ {cmd}")
    if wait:
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0
    else:
        proc = subprocess.Popen(cmd, shell=True)
        return proc


def pause(seconds=2):
    """Pause for a few seconds."""
    time.sleep(seconds)


def main():
    """Run the demo."""
    print_header("QueueCTL Interactive Demo")
    print("\nThis demo will showcase all features of QueueCTL.")
    print("Press Ctrl+C at any time to exit.")
    
    input("\nPress Enter to start the demo...")
    
    # Clean up (best effort). If file is in use (Windows), skip deletion.
    if os.path.exists("queuectl.db"):
        try:
            os.remove("queuectl.db")
            print("✓ Cleaned up previous database")
        except PermissionError as e:
            print("! Skipping database cleanup: file is in use (queuectl.db)")
        except OSError as e:
            # WinError 32 or similar: file in use
            if getattr(e, 'winerror', None) == 32:
                print("! Skipping database cleanup: file is in use (WinError 32)")
            else:
                print(f"! Skipping database cleanup due to OS error: {e}")
    
    # Step 1: Show configuration
    print_step(1, "Show Default Configuration")
    run_cmd("python -m queuectl.cli config show")
    pause()
    
    # Step 2: Enqueue some jobs
    print_step(2, "Enqueue Multiple Jobs")
    
    jobs = [
        {"id": "job-1", "command": "echo Hello from Job 1"},
        {"id": "job-2", "command": "echo Processing Job 2 && timeout /t 2" if os.name == 'nt' else "echo Processing Job 2 && sleep 2"},
        {"id": "job-3", "command": "echo Job 3 completed"},
        {"id": "job-fail", "command": "exit 1", "max_retries": 2},
        {"id": "job-4", "command": "echo Final job"},
    ]
    
    for job in jobs:
        job_json = json.dumps(job)
        # Properly quote JSON for the current OS/shell
        if os.name == 'nt':
            # On Windows (cmd.exe), escape double quotes by doubling them
            job_arg = f'"{job_json.replace("\"", '""')}"'
        else:
            # On POSIX shells, wrap JSON in single quotes
            job_arg = f"'{job_json}'"
        run_cmd(f'python -m queuectl.cli enqueue {job_arg}')
        pause(0.5)
    
    # Step 3: Check status
    print_step(3, "Check Queue Status")
    run_cmd("python -m queuectl.cli status")
    pause()
    
    # Step 4: List pending jobs
    print_step(4, "List Pending Jobs")
    run_cmd("python -m queuectl.cli list --state pending")
    pause()
    
    # Step 5: Start workers
    print_step(5, "Start 2 Workers (will run for 20 seconds)")
    print("Workers will process jobs and handle retries...")
    
    worker_proc = run_cmd("python -m queuectl.cli worker start --count 2", wait=False)
    
    # Let workers run
    print("\nWorkers are running...")
    for i in range(20):
        print(f"  {i+1}/20 seconds elapsed...", end="\r")
        time.sleep(1)
    
    print("\n\nStopping workers...")
    worker_proc.terminate()
    worker_proc.wait()
    pause(2)
    
    # Step 6: Check status after processing
    print_step(6, "Check Status After Processing")
    run_cmd("python -m queuectl.cli status")
    pause()
    
    # Step 7: List completed jobs
    print_step(7, "List Completed Jobs")
    run_cmd("python -m queuectl.cli list --state completed")
    pause()
    
    # Step 8: Check DLQ
    print_step(8, "Check Dead Letter Queue")
    run_cmd("python -m queuectl.cli dlq list")
    pause()
    
    # Step 9: Get job details
    print_step(9, "Get Detailed Job Information")
    run_cmd("python -m queuectl.cli info job-fail")
    pause()
    
    # Step 10: Retry from DLQ
    print_step(10, "Retry Job from DLQ")
    run_cmd("python -m queuectl.cli dlq retry job-fail")
    pause()
    
    run_cmd("python -m queuectl.cli info job-fail")
    pause()
    
    # Step 11: Update configuration
    print_step(11, "Update Configuration")
    run_cmd("python -m queuectl.cli config set max-retries 5")
    run_cmd("python -m queuectl.cli config set backoff-base 3")
    run_cmd("python -m queuectl.cli config show")
    pause()
    
    # Step 12: Final status
    print_step(12, "Final Status")
    run_cmd("python -m queuectl.cli status")
    
    # Summary
    print_header("Demo Complete!")
    print("\n✓ Demonstrated Features:")
    print("  • Job enqueuing")
    print("  • Multiple workers")
    print("  • Automatic retry with exponential backoff")
    print("  • Dead Letter Queue (DLQ)")
    print("  • Job status monitoring")
    print("  • Configuration management")
    print("  • Job persistence")
    
    print("\n📚 For more information, see README.md")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✓ Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
