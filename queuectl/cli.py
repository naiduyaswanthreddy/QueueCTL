"""CLI interface for QueueCTL."""

import click
import json
import sys
import subprocess
from datetime import datetime
from tabulate import tabulate

from .database import Database
from .queue_manager import QueueManager
from .models import Job, JobState, Config
from .worker import start_workers
from .web import create_app


# Global database path
DB_PATH = "queuectl.db"


@click.group()
@click.version_option(version='1.0.0')
@click.option('--db', default=DB_PATH, help='Database path (global, can be overridden per command)')
@click.pass_context
def cli(ctx, db):
    """QueueCTL - A CLI-based background job queue system.
    
    Manage background jobs with worker processes, automatic retries,
    and a Dead Letter Queue for failed jobs.
    """
    ctx.ensure_object(dict)
    ctx.obj['db'] = db


@cli.command()
@click.argument('job_json')
@click.option('--db', default=None, help='Database path')
@click.pass_context
def enqueue(ctx, job_json, db):
    """Enqueue a new job.
    
    JOB_JSON should be a JSON string containing job details.
    
    Example:
        queuectl enqueue '{"id":"job1","command":"echo Hello"}'
    """
    try:
        # Parse job JSON
        job_data = json.loads(job_json)
        
        # Validate required fields
        if 'id' not in job_data or 'command' not in job_data:
            click.echo("Error: Job must contain 'id' and 'command' fields", err=True)
            sys.exit(1)
        
        # Optional fields
        priority = int(job_data.get('priority', 0))
        run_at = job_data.get('run_at')
        run_at_dt = datetime.fromisoformat(run_at) if run_at else None
        timeout_seconds = int(job_data['timeout_seconds']) if 'timeout_seconds' in job_data and job_data['timeout_seconds'] is not None else None

        # Create job
        job = Job(
            id=job_data['id'],
            command=job_data['command'],
            max_retries=job_data.get('max_retries'),  # None -> default from config
            priority=priority,
            run_at=run_at_dt,
            timeout_seconds=timeout_seconds,
        )
        
        # Enqueue job
        database = Database(db or ctx.obj.get('db', DB_PATH))
        queue_manager = QueueManager(database)
        queue_manager.enqueue_job(job)
        
        click.echo(f"Job '{job.id}' enqueued successfully")
        click.echo(f"  Command: {job.command}")
        click.echo(f"  Max retries: {job.max_retries}")
        if run_at_dt:
            click.echo(f"  Run at: {run_at_dt.isoformat()}")
        if priority:
            click.echo(f"  Priority: {priority}")
        if timeout_seconds is not None:
            click.echo(f"  Timeout: {timeout_seconds}s")
        
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON - {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def worker():
    """Manage worker processes."""
    pass


@cli.group()
def web():
    """Minimal web dashboard for monitoring."""
    pass


@web.command("start")
@click.option('--port', default=5000, help='Port to run the web dashboard on')
@click.option('--db', default=None, help='Database path')
@click.pass_context
def web_start(ctx, port, db):
    """Start the web dashboard.
    
    Example:
        queuectl web start --port 5000
    """
    database_path = db or ctx.obj.get('db', DB_PATH)
    app = create_app(database_path)
    app.run(host='0.0.0.0', port=port, debug=False)


@cli.group()
def workers():
    """Inspect worker registry."""
    pass


@workers.command("list")
@click.option('--db', default=None, help='Database path')
@click.pass_context
def workers_list(ctx, db):
    """List registered workers and their heartbeat status.
    
    Example:
        queuectl workers list
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        rows = database.list_workers()
        if not rows:
            click.echo("No workers found.")
            return
        table = []
        for r in rows:
            status = 'stopped' if r.get('stopped_at') else 'active'
            table.append([
                r.get('id', '')[:20],
                r.get('pid', ''),
                r.get('name', ''),
                r.get('started_at', ''),
                r.get('last_heartbeat', ''),
                r.get('stopped_at', '') or '',
                status,
            ])
        click.echo(tabulate(
            table,
            headers=['ID', 'PID', 'Name', 'Started', 'Last Heartbeat', 'Stopped', 'Status'],
            tablefmt='grid'
        ))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@worker.command()
@click.option('--count', default=1, help='Number of workers to start')
@click.option('--db', default=None, help='Database path')
@click.pass_context
def start(ctx, count, db):
    """Start worker processes.
    
    Example:
        queuectl worker start --count 3
    """
    click.echo(f"Starting {count} worker(s)...")
    click.echo("Press Ctrl+C to stop gracefully")
    click.echo("-" * 50)
    
    try:
        start_workers(count, db or ctx.obj.get('db', DB_PATH))
    except KeyboardInterrupt:
        click.echo("\nWorkers stopped")


@worker.command()
def stop():
    """Stop running workers gracefully.
    
    Note: This is handled by Ctrl+C when workers are running.
    For background workers, you would need to implement process management.
    """
    click.echo("To stop workers, press Ctrl+C in the terminal where they are running.")
    click.echo("Workers will finish their current jobs before stopping.")


@cli.command()
@click.option('--db', default=None, help='Database path')
@click.pass_context
def status(ctx, db):
    """Show summary of all job states and active workers.
    
    Example:
        queuectl status
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        queue_manager = QueueManager(database)
        
        # Get statistics
        stats = queue_manager.get_statistics()
        # Get active workers (heartbeats within last 10s)
        active_workers = database.get_active_workers(stale_seconds=10)
        
        click.echo("\n" + "=" * 50)
        click.echo("QueueCTL Status")
        click.echo("=" * 50)
        
        # Job statistics
        click.echo("\nJob Statistics:")
        click.echo("-" * 50)
        
        table_data = [
            ["Total Jobs", stats['total']],
            ["Pending", stats['pending']],
            ["Processing", stats['processing']],
            ["Completed", stats['completed']],
            ["Failed (Retrying)", stats['failed']],
            ["Dead (DLQ)", stats['dead']],
        ]
        
        click.echo(tabulate(table_data, tablefmt='simple'))

        # Workers
        click.echo("\nWorkers:")
        click.echo("-" * 50)
        click.echo(tabulate([["Active Workers", active_workers]], tablefmt='simple'))

        # Metrics
        click.echo("\nMetrics:")
        click.echo("-" * 50)
        metrics = database.get_metrics()
        mtable = [
            ["Average Duration (last 20)", f"{metrics.get('avg_duration_ms') or 'n/a'} ms"],
            ["Completed Last Minute", metrics.get('completed_last_min', 0)],
        ]
        click.echo(tabulate(mtable, tablefmt='simple'))
        
        # Show recent jobs
        if stats['total'] > 0:
            click.echo("\nRecent Jobs:")
            click.echo("-" * 50)
            
            jobs = queue_manager.get_all_jobs()[:10]  # Show last 10 jobs
            
            job_table = []
            for job in jobs:
                job_table.append([
                    job.id[:20],
                    job.state.value,
                    f"{job.attempts}/{job.max_retries}",
                    job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                ])
            
            click.echo(tabulate(
                job_table,
                headers=['Job ID', 'State', 'Attempts', 'Created At'],
                tablefmt='grid'
            ))
        
        click.echo()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--state', type=click.Choice(['pending', 'processing', 'completed', 'failed', 'dead']), 
              help='Filter by job state')
@click.option('--db', default=None, help='Database path')
@click.pass_context
def list(ctx, state, db):
    """List jobs, optionally filtered by state.
    
    Example:
        queuectl list --state pending
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        queue_manager = QueueManager(database)
        
        # Get jobs
        if state:
            jobs = queue_manager.get_jobs_by_state(JobState(state))
            click.echo(f"\nJobs with state: {state}")
        else:
            jobs = queue_manager.get_all_jobs()
            click.echo("\nAll Jobs")
        
        click.echo("-" * 80)
        
        if not jobs:
            click.echo("No jobs found.")
            return
        
        # Prepare table data
        table_data = []
        for job in jobs:
            error_preview = ""
            if job.error_message:
                error_preview = job.error_message[:40] + "..." if len(job.error_message) > 40 else job.error_message
            
            table_data.append([
                job.id[:20],
                job.command[:30] + "..." if len(job.command) > 30 else job.command,
                job.state.value,
                f"{job.attempts}/{job.max_retries}",
                job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                error_preview
            ])
        
        click.echo(tabulate(
            table_data,
            headers=['Job ID', 'Command', 'State', 'Attempts', 'Created At', 'Error'],
            tablefmt='grid'
        ))
        click.echo(f"\nTotal: {len(jobs)} job(s)")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def dlq():
    """Manage Dead Letter Queue (DLQ)."""
    pass


@dlq.command()
@click.option('--db', default=None, help='Database path')
@click.pass_context
def list(ctx, db):
    """List all jobs in the Dead Letter Queue.
    
    Example:
        queuectl dlq list
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        queue_manager = QueueManager(database)
        
        jobs = queue_manager.get_jobs_by_state(JobState.DEAD)
        
        click.echo("\nDead Letter Queue")
        click.echo("-" * 80)
        
        if not jobs:
            click.echo("No jobs in DLQ.")
            return
        
        # Prepare table data
        table_data = []
        for job in jobs:
            table_data.append([
                job.id[:20],
                job.command[:30] + "..." if len(job.command) > 30 else job.command,
                f"{job.attempts}/{job.max_retries}",
                job.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                job.error_message[:40] + "..." if job.error_message and len(job.error_message) > 40 else job.error_message or ""
            ])
        
        click.echo(tabulate(
            table_data,
            headers=['Job ID', 'Command', 'Attempts', 'Failed At', 'Error'],
            tablefmt='grid'
        ))
        click.echo(f"\nTotal: {len(jobs)} job(s) in DLQ")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@dlq.command()
@click.argument('job_id')
@click.option('--db', default=None, help='Database path')
@click.pass_context
def retry(ctx, job_id, db):
    """Retry a job from the Dead Letter Queue.
    
    Example:
        queuectl dlq retry job1
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        queue_manager = QueueManager(database)
        
        if queue_manager.retry_dlq_job(job_id):
            click.echo(f"Job '{job_id}' moved from DLQ to pending queue")
        else:
            click.echo(f"Error: Could not retry job '{job_id}'", err=True)
            sys.exit(1)
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def config():
    """Manage configuration settings."""
    pass


@config.command()
@click.argument('key')
@click.argument('value')
@click.option('--db', default=None, help='Database path')
@click.pass_context
def set(ctx, key, value, db):
    """Set a configuration value.
    
    Available keys:
        max-retries: Maximum number of retry attempts (integer)
        backoff-base: Base for exponential backoff calculation (integer)
        worker-poll-interval: Worker polling interval in seconds (float)
    
    Example:
        queuectl config set max-retries 5
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        current_config = database.get_config()
        
        # Map CLI keys to config attributes
        key_map = {
            'max-retries': 'max_retries',
            'backoff-base': 'backoff_base',
            'worker-poll-interval': 'worker_poll_interval',
        }
        
        if key not in key_map:
            click.echo(f"Error: Unknown config key '{key}'", err=True)
            click.echo("Available keys: max-retries, backoff-base, worker-poll-interval")
            sys.exit(1)
        
        attr_name = key_map[key]
        
        # Convert value to appropriate type
        if attr_name in ['max_retries', 'backoff_base']:
            value = int(value)
        elif attr_name == 'worker_poll_interval':
            value = float(value)
        
        # Update config
        setattr(current_config, attr_name, value)
        database.save_config(current_config)
        
        click.echo(f"Configuration updated: {key} = {value}")
        
    except ValueError as e:
        click.echo(f"Error: Invalid value type - {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@config.command()
@click.option('--db', default=None, help='Database path')
@click.pass_context
def show(ctx, db):
    """Show current configuration.
    
    Example:
        queuectl config show
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        current_config = database.get_config()
        
        click.echo("\nCurrent Configuration:")
        click.echo("-" * 50)
        
        table_data = [
            ["max-retries", current_config.max_retries],
            ["backoff-base", current_config.backoff_base],
            ["worker-poll-interval", f"{current_config.worker_poll_interval}s"],
        ]
        
        click.echo(tabulate(table_data, headers=['Key', 'Value'], tablefmt='simple'))
        click.echo()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('job_id')
@click.option('--db', default=None, help='Database path')
@click.pass_context
def info(ctx, job_id, db):
    """Show detailed information about a specific job.
    
    Example:
        queuectl info job1
    """
    try:
        database = Database(db or ctx.obj.get('db', DB_PATH))
        queue_manager = QueueManager(database)
        
        job = queue_manager.get_job_status(job_id)
        
        if not job:
            click.echo(f"Error: Job '{job_id}' not found", err=True)
            sys.exit(1)
        
        click.echo("\nJob Details:")
        click.echo("=" * 50)
        click.echo(f"ID:              {job.id}")
        click.echo(f"Command:         {job.command}")
        click.echo(f"State:           {job.state.value}")
        click.echo(f"Attempts:        {job.attempts}/{job.max_retries}")
        click.echo(f"Created At:      {job.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Updated At:      {job.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if job.completed_at:
            click.echo(f"Completed At:    {job.completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if job.next_retry_at:
            click.echo(f"Next Retry At:   {job.next_retry_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if job.error_message:
            click.echo(f"\nError Message:")
            click.echo("-" * 50)
            click.echo(job.error_message)
        
        # Show captured output and timing if available
        if job.last_stdout or job.last_stderr or job.duration_ms is not None:
            click.echo(f"\nExecution Details:")
            click.echo("-" * 50)
            if job.duration_ms is not None:
                click.echo(f"Duration:       {job.duration_ms} ms")
            if job.last_stdout:
                click.echo("\nStdout:")
                click.echo(job.last_stdout)
            if job.last_stderr:
                click.echo("\nStderr:")
                click.echo(job.last_stderr)
        
        click.echo()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
