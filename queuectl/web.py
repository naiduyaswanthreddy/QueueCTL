"""Minimal Flask web dashboard for QueueCTL with simulation mode."""

from flask import Flask, jsonify, request, render_template_string, redirect, url_for, Response
import threading
import time
import queue as queue_lib
from .database import Database
from .queue_manager import QueueManager
from .models import JobState


BASE_HTML = """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>QueueCTL Dashboard</title>
  <link rel=\"stylesheet\" href=\"{{ url_for('static', filename='base.css') }}\" />
  <script src=\"https://cdn.tailwindcss.com\" defer></script>
  <script>
    (function(){
      function load(src, cb){ var s=document.createElement('script'); s.src=src; s.onload=cb; s.onerror=cb; document.head.appendChild(s); }
      function ensure(cb){ if(window.tailwind){ cb(true); return; } load('https://cdn.tailwindcss.com', function(){ cb(!!window.tailwind); }); }
      ensure(function(ok){
        if(!ok){
          load('https://unpkg.com/tailwindcss-cdn@3.4.1/tailwindcss.js', function(){
            if(!window.tailwind){
              document.head.insertAdjacentHTML('beforeend', '<style>body{font-family:system-ui,Segoe UI,Arial;margin:0;} .border{border:1px solid #e5e7eb}.rounded{border-radius:0.375rem}.p-4{padding:1rem}.p-6{padding:1.5rem}.text-sm{font-size:.875rem}.text-lg{font-size:1.125rem;font-weight:600}.flex{display:flex}.grid{display:grid}.min-h-screen{min-height:100vh}.w-64{width:16rem}.space-y-3>*+*{margin-top:.75rem}.space-y-1>*+*{margin-top:.25rem}.px-2{padding-left:.5rem;padding-right:.5rem}.px-3{padding-left:.75rem;padding-right:.75rem}.py-1{padding-top:.25rem;padding-bottom:.25rem}.rounded{border-radius:.375rem}.bg-blue-600{background:#2563eb;color:#fff}.text-white{color:#fff}.dark .dark\\:bg-gray-900{background:#111827}.bg-gray-50{background:#f9fafb}.text-gray-900{color:#111827}</style>');
            }
          });
        }
      });
    })();
  </script>
  <script>
    // Tailwind CDN fallback: try alternate CDN, else inject minimal styles
    (function(){
      function load(src, cb){ var s=document.createElement('script'); s.src=src; s.onload=cb; s.onerror=cb; document.head.appendChild(s); }
      function ensure(cb){ if(window.tailwind){ cb(true); return; } load('https://cdn.tailwindcss.com', function(){ cb(!!window.tailwind); }); }
      ensure(function(ok){
        if(!ok){
          load('https://unpkg.com/tailwindcss-cdn@3.4.1/tailwindcss.js', function(){
            if(!window.tailwind){
              document.head.insertAdjacentHTML('beforeend', '<style>body{font-family:system-ui,Segoe UI,Arial;margin:0;} .border{border:1px solid #e5e7eb}.rounded{border-radius:0.375rem}.p-4{padding:1rem}.p-6{padding:1.5rem}.text-sm{font-size:.875rem}.text-lg{font-size:1.125rem;font-weight:600}.flex{display:flex}.grid{display:grid}.min-h-screen{min-height:100vh}.w-64{width:16rem}.space-y-3>*+*{margin-top:.75rem}.space-y-1>*+*{margin-top:.25rem}.px-2{padding-left:.5rem;padding-right:.5rem}.px-3{padding-left:.75rem;padding-right:.75rem}.py-1{padding-top:.25rem;padding-bottom:.25rem}.rounded{border-radius:.375rem}.bg-blue-600{background:#2563eb;color:#fff}.text-white{color:#fff}.dark .dark\\:bg-gray-900{background:#111827}.bg-gray-50{background:#f9fafb}.text-gray-900{color:#111827}</style>');
            }
          });
        }
      });
    })();
  </script>
</head>
<body class=\"bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100\">
  <div class=\"flex min-h-screen\">
    <aside class=\"w-64 border-r border-gray-200 dark:border-gray-800 p-4 space-y-3\">
      <div class=\"flex items-center justify-between\">
        <h1 class=\"text-xl font-bold\">QueueCTL</h1>
        <button id=\"themeBtn\" class=\"px-2 py-1 text-xs border rounded\">Theme</button>
      </div>
      <nav class=\"space-y-1 text-sm\">
        <a class=\"block hover:underline\" href=\"{{ url_for('index') }}\">Dashboard</a>
        <a class=\"block hover:underline\" href=\"{{ url_for('jobs') }}\">Jobs</a>
        <a class=\"block hover:underline\" href=\"{{ url_for('workers') }}\">Workers</a>
        <a class=\"block hover:underline\" href=\"/metrics\">Metrics</a>
        <a class=\"block hover:underline\" href=\"/simulate\"><b>Start from Beginning</b></a>
      </nav>
    </aside>
    <main class=\"flex-1 p-6\">
      {{ content|safe }}
    </main>
  </div>
  <script>
    document.getElementById('themeBtn').onclick = function(){
      document.documentElement.classList.toggle('dark');
    };
  </script>
</body>
</html>
"""

INDEX_BODY = """
<div class=\"flex items-center justify-between\">
  <h2 class=\"text-lg font-semibold\">Dashboard Overview</h2>
  <a href=\"/simulate\" class=\"px-3 py-1 bg-blue-600 text-white rounded text-sm\">▶ Start from Beginning</a>
</div>

<div class=\"grid grid-cols-2 md:grid-cols-3 gap-4 mt-4\">
  <div class=\"p-4 border rounded\"><div class=\"text-xs text-gray-500\">Total</div><div class=\"text-2xl\">{{ stats.total }}</div></div>
  <div class=\"p-4 border rounded\"><div class=\"text-xs text-gray-500\">Pending</div><div class=\"text-2xl\">{{ stats.pending }}</div></div>
  <div class=\"p-4 border rounded\"><div class=\"text-xs text-gray-500\">Processing</div><div class=\"text-2xl\">{{ stats.processing }}</div></div>
  <div class=\"p-4 border rounded\"><div class=\"text-xs text-gray-500\">Completed</div><div class=\"text-2xl\">{{ stats.completed }}</div></div>
  <div class=\"p-4 border rounded\"><div class=\"text-xs text-gray-500\">Failed</div><div class=\"text-2xl\">{{ stats.failed }}</div></div>
  <div class=\"p-4 border rounded\"><div class=\"text-xs text-gray-500\">Dead</div><div class=\"text-2xl\">{{ stats.dead }}</div></div>
</div>

<div class=\"grid grid-cols-2 gap-4 mt-6\">
  <div class=\"p-4 border rounded\">
    <h3 class=\"font-medium\">Workers</h3>
    <div class=\"mt-2 text-sm\"><b>Active:</b> {{ active_workers }}</div>
  </div>
  <div class=\"p-4 border rounded\">
    <h3 class=\"font-medium\">Metrics</h3>
    <div class=\"mt-2 text-sm\"><b>Average Duration (last 20):</b> {{ metrics.avg_duration_ms or 'n/a' }} ms</div>
    <div class=\"mt-1 text-sm\"><b>Completed Last Minute:</b> {{ metrics.completed_last_min }}</div>
  </div>
</div>

<div class=\"mt-6 border rounded\">
  <div class=\"px-4 py-2 border-b font-medium\">Recent Jobs</div>
  <div class=\"overflow-x-auto\">
  <table class=\"min-w-full text-sm\">
    <thead class=\"bg-gray-100 dark:bg-gray-800\">
      <tr>
        <th class=\"text-left p-2\">ID</th>
        <th class=\"text-left p-2\">State</th>
        <th class=\"text-left p-2\">Attempts</th>
        <th class=\"text-left p-2\">Created</th>
      </tr>
    </thead>
    <tbody>
    {% for j in jobs %}
      <tr class=\"border-t border-gray-200 dark:border-gray-800\">
        <td class=\"p-2\">{{ j.id }}</td>
        <td class=\"p-2\"><span class=\"px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-700\">{{ j.state.value }}</span></td>
        <td class=\"p-2\">{{ j.attempts }}/{{ j.max_retries }}</td>
        <td class=\"p-2\">{{ j.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
"""


# Simulation page body (wrapped by BASE_HTML)
SIMULATE_BODY = """
<div class=\"flex items-center justify-between\">
  <h2 class=\"text-lg font-semibold\">Start from Beginning</h2>
  <div class=\"space-x-2\">
    <button id=\"startBtn\" class=\"px-3 py-1 bg-blue-600 text-white rounded\">▶ Start</button>
    <button id=\"resetBtn\" class=\"px-3 py-1 border rounded\">Reset</button>
    <label class=\"ml-3 text-sm\">Speed <input id=\"speed\" type=\"range\" min=\"0.25\" max=\"3\" step=\"0.25\" value=\"1\"/></label>
  </div>
</div>
<div class=\"grid grid-cols-3 gap-4 mt-4\">
  <section class=\"col-span-2 border rounded p-4\">
    <h3 class=\"font-medium\">Storyboard</h3>
    <div id=\"story\" class=\"mt-2 text-sm space-y-2\"></div>
  </section>
  <section class=\"border rounded p-4\">
    <h3 class=\"font-medium\">Live Logs</h3>
    <pre id=\"logs\" class=\"mt-2 text-xs h-80 overflow-auto bg-black text-green-300 p-2 rounded\"></pre>
  </section>
</div>
<div class=\"grid grid-cols-3 gap-4 mt-4\">
  <section class=\"border rounded p-4\">
    <h3 class=\"font-medium\">Queue</h3>
    <div id=\"queue\" class=\"text-sm space-y-1\"></div>
  </section>
  <section class=\"border rounded p-4\">
    <h3 class=\"font-medium\">Workers</h3>
    <div id=\"workers\" class=\"text-sm space-y-1\"></div>
  </section>
  <section class=\"border rounded p-4\">
    <h3 class=\"font-medium\">DLQ</h3>
    <div id=\"dlq\" class=\"text-sm space-y-1\"></div>
  </section>
</div>
<script>
  const qs = (s)=>document.querySelector(s);
  const story = qs('#story');
  const logs = qs('#logs');
  const qdiv = qs('#queue');
  const wdiv = qs('#workers');
  const ddiv = qs('#dlq');
  function renderState(s){
    qdiv.innerHTML = (s.queue||[]).map(j=>`<div class=\"px-2 py-1 rounded bg-gray-100 dark:bg-gray-800\">${j.id} <span class=\"text-xs\">(${j.state||'pending'})</span></div>`).join('');
    wdiv.innerHTML = (s.workers||[]).map(w=>`<div class=\"px-2 py-1 rounded bg-gray-100 dark:bg-gray-800\">${w.id} - ${w.status}${w.job?` <span class=\"text-xs\">${w.job.id} ${w.job.progress||0}%</span>`:''}</div>`).join('');
    ddiv.innerHTML = (s.dlq||[]).map(j=>`<div class=\"px-2 py-1 rounded bg-orange-100 dark:bg-orange-900\">${j.id}</div>`).join('');
  }
  function appendStory(t){ const el = document.createElement('div'); el.textContent=t; story.appendChild(el); story.scrollTop=story.scrollHeight; }
  function appendLog(l){ logs.textContent += `\n[${new Date().toLocaleTimeString()}] ${l}`; logs.scrollTop=logs.scrollHeight; }
  function startSSE(){
    const ev = new EventSource('/api/simulate/stream');
    ev.onmessage = (e)=>{
      try{
        const d = JSON.parse(e.data);
        if(d.type==='init') appendStory(d.msg);
        if(d.type==='enqueue') appendStory(d.msg);
        if(d.type==='assign') appendStory(`${d.worker} picked ${d.job}`);
        if(d.type==='progress') appendStory(`${d.worker} ${d.job} ${d.pct}%`);
        if(d.type==='fail') appendStory(`Job ${d.job} failed. Retrying in ${d.backoff}s…`);
        if(d.type==='backoff') appendStory(`Job ${d.job} retry in ${d.in}s`);
        if(d.type==='complete') appendStory(`Job ${d.job} completed ✅`);
        if(d.type==='done') appendStory(d.msg);
        appendLog(d.type+ (d.msg?`: ${d.msg}`:''));
        fetch('/api/simulate/status').then(r=>r.json()).then(renderState);
      }catch(err){ console.error(err); }
    };
    ev.onerror = ()=>{ ev.close(); };
  }
  qs('#startBtn').onclick = async ()=>{
    const speed = parseFloat(qs('#speed').value||'1');
    await fetch('/api/simulate/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({speed})});
    startSSE();
  };
  qs('#resetBtn').onclick = async ()=>{
    await fetch('/api/simulate/reset',{method:'POST'});
    story.innerHTML=''; logs.textContent=''; qdiv.innerHTML=''; wdiv.innerHTML=''; ddiv.innerHTML='';
  };
</script>
"""

JOBS_BODY = """
<div class=\"flex items-center justify-between\">
  <h2 class=\"text-lg font-semibold\">Jobs {% if state %}<span class=\"text-xs text-gray-500\">(state={{ state }})</span>{% endif %}</h2>
</div>
<div class=\"mt-4 border rounded\">
  <div class=\"overflow-x-auto\">
  <table class=\"min-w-full text-sm\">
    <thead class=\"bg-gray-100 dark:bg-gray-800\">
      <tr>
        <th class=\"text-left p-2\">ID</th>
        <th class=\"text-left p-2\">Command</th>
        <th class=\"text-left p-2\">State</th>
        <th class=\"text-left p-2\">Attempts</th>
        <th class=\"text-left p-2\">Priority</th>
        <th class=\"text-left p-2\">Run At</th>
        <th class=\"text-left p-2\">Error</th>
      </tr>
    </thead>
    <tbody>
    {% for j in jobs %}
      <tr class=\"border-t border-gray-200 dark:border-gray-800\">
        <td class=\"p-2\">{{ j.id }}</td>
        <td class=\"p-2\">{{ j.command }}</td>
        <td class=\"p-2\"><span class=\"px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-700\">{{ j.state.value }}</span></td>
        <td class=\"p-2\">{{ j.attempts }}/{{ j.max_retries }}</td>
        <td class=\"p-2\">{{ j.priority }}</td>
        <td class=\"p-2\">{{ j.run_at.strftime('%Y-%m-%d %H:%M:%S') if j.run_at else '' }}</td>
        <td class=\"p-2\">{{ (j.error_message or '')[:60] }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
"""

WORKERS_BODY = """
<h2 class=\"text-lg font-semibold\">Workers</h2>
<div class=\"mt-4 border rounded\">
  <div class=\"overflow-x-auto\">
  <table class=\"min-w-full text-sm\">
    <thead class=\"bg-gray-100 dark:bg-gray-800\">
      <tr>
        <th class=\"text-left p-2\">ID</th>
        <th class=\"text-left p-2\">PID</th>
        <th class=\"text-left p-2\">Name</th>
        <th class=\"text-left p-2\">Started</th>
        <th class=\"text-left p-2\">Last Heartbeat</th>
        <th class=\"text-left p-2\">Stopped</th>
        <th class=\"text-left p-2\">Status</th>
      </tr>
    </thead>
    <tbody>
    {% for w in workers %}
      <tr class=\"border-t border-gray-200 dark:border-gray-800\">
        <td class=\"p-2\">{{ w.id }}</td>
        <td class=\"p-2\">{{ w.pid }}</td>
        <td class=\"p-2\">{{ w.name }}</td>
        <td class=\"p-2\">{{ w.started_at }}</td>
        <td class=\"p-2\">{{ w.last_heartbeat }}</td>
        <td class=\"p-2\">{{ w.stopped_at or '' }}</td>
        <td class=\"p-2\">{{ 'stopped' if w.stopped_at else 'active' }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
</div>
"""


def create_app(db_path: str = "queuectl.db") -> Flask:
    app = Flask(__name__)

    def _db() -> Database:
        return Database(db_path)

    @app.route("/")
    def index():
        db = _db()
        qm = QueueManager(db)
        stats = qm.get_statistics()
        active_workers = db.get_active_workers(stale_seconds=10)
        metrics = db.get_metrics()
        jobs = qm.get_all_jobs()[:10]
        body = render_template_string(INDEX_BODY, stats=stats, active_workers=active_workers, metrics=metrics, jobs=jobs)
        return render_template_string(BASE_HTML, content=body)

    @app.route("/jobs")
    def jobs():
        db = _db()
        qm = QueueManager(db)
        state = request.args.get('state')
        jobs = qm.get_jobs_by_state(JobState(state)) if state else qm.get_all_jobs()
        body = render_template_string(JOBS_BODY, jobs=jobs, state=state)
        return render_template_string(BASE_HTML, content=body)

    @app.route("/workers")
    def workers():
        db = _db()
        rows = db.list_workers()
        body = render_template_string(WORKERS_BODY, workers=rows)
        return render_template_string(BASE_HTML, content=body)

    @app.route("/api/status")
    def api_status():
        db = _db()
        qm = QueueManager(db)
        return jsonify({
            "stats": qm.get_statistics(),
            "active_workers": db.get_active_workers(stale_seconds=10),
            "metrics": db.get_metrics(),
        })

    @app.route("/metrics")
    def metrics():
        db = _db()
        qm = QueueManager(db)
        stats = qm.get_statistics()
        active_workers = db.get_active_workers(stale_seconds=10)
        m = db.get_metrics()

        # Prometheus exposition format (text/plain; version=0.0.4)
        lines = []
        lines.append("# HELP queue_jobs_total Number of jobs by state")
        lines.append("# TYPE queue_jobs_total gauge")
        for state_key in ["pending", "processing", "completed", "failed", "dead"]:
            lines.append(f'queue_jobs_total{{state="{state_key}"}} {stats.get(state_key, 0)}')

        lines.append("# HELP queue_active_workers Active workers based on recent heartbeats")
        lines.append("# TYPE queue_active_workers gauge")
        lines.append(f"queue_active_workers {active_workers}")

        lines.append("# HELP queue_avg_duration_ms Average job duration over last 20 completed jobs")
        lines.append("# TYPE queue_avg_duration_ms gauge")
        avg_ms = m.get("avg_duration_ms") or 0
        lines.append(f"queue_avg_duration_ms {avg_ms}")

        lines.append("# HELP queue_completed_last_min Number of jobs completed in the last minute")
        lines.append("# TYPE queue_completed_last_min counter")
        lines.append(f"queue_completed_last_min {m.get('completed_last_min', 0)}")

        return ("\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})

    # ---------------- Simulation (MVP) ----------------
    sim_lock = threading.Lock()
    sim_events: "queue_lib.Queue[dict]" = queue_lib.Queue()
    sim_state = {
        "running": False,
        "step": "idle",
        "speed": 1.0,
        "queue": [],
        "workers": [],
        "dlq": [],
        "logs": [],
        "stats": {"total": 0, "completed": 0, "failed": 0, "retries": 0, "workers": 0},
    }

    def _emit(evt: dict):
        evt["ts"] = time.time()
        sim_events.put(evt)
        with sim_lock:
            sim_state["logs"].append(evt)

    def _sleep(sec: float):
        time.sleep(max(0.05, sec / max(sim_state.get("speed", 1.0), 0.1)))

    def _run_simulation(jobs):
        # Phases storyboard
        with sim_lock:
            sim_state.update({
                "running": True,
                "step": "init",
                "queue": [],
                "workers": [
                    {"id": "worker-1", "status": "idle", "job": None, "hb": True},
                    {"id": "worker-2", "status": "idle", "job": None, "hb": True},
                ],
                "dlq": [],
                "logs": [],
                "stats": {"total": len(jobs), "completed": 0, "failed": 0, "retries": 0, "workers": 2},
            })
        _emit({"type": "init", "msg": "Loading configuration…"})
        _sleep(0.6)
        _emit({"type": "init", "msg": "Connecting to SQLite database…"})
        _sleep(0.6)
        _emit({"type": "init", "msg": "Starting worker pool…"})
        _sleep(0.6)

        # Enqueue
        with sim_lock:
            sim_state["step"] = "enqueue"
            sim_state["queue"] = [{"id": j["id"], "command": j["command"], "state": "pending", "attempt": 0, "max": j.get("max_retries", 3)} for j in jobs]
        for j in jobs:
            _emit({"type": "enqueue", "job": j["id"], "msg": f"Enqueued {j['id']}: {j['command']}"})
            _sleep(0.4)

        # Assign to workers
        with sim_lock:
            sim_state["step"] = "assign"
        for i, w in enumerate(sim_state["workers"]):
            with sim_lock:
                if not sim_state["queue"]:
                    break
                job = sim_state["queue"].pop(0)
                w["status"] = "busy"
                w["job"] = {"id": job["id"], "progress": 0}
            _emit({"type": "assign", "worker": w["id"], "job": job["id"]})
            _sleep(0.3)

        # Processing loop
        with sim_lock:
            sim_state["step"] = "processing"
        ticks = 0
        while True:
            done = True
            with sim_lock:
                for w in sim_state["workers"]:
                    if w["job"] is None:
                        continue
                    done = False
                    w["job"]["progress"] = min(100, w["job"]["progress"] + 25)
                    _emit({"type": "progress", "worker": w["id"], "job": w["job"]["id"], "pct": w["job"]["progress"]})
                    if w["job"]["progress"] >= 100:
                        # Simulate outcome: first job success, second job fails twice then DLQ
                        job_id = w["job"]["id"]
                        if job_id.endswith("1"):
                            _emit({"type": "complete", "job": job_id})
                            sim_state["stats"]["completed"] += 1
                            w["status"] = "idle"
                            w["job"] = None
                        else:
                            # Mark as failed and handle backoff
                            # Find job meta in a shadow list
                            failed_attempt = 1
                            _emit({"type": "fail", "job": job_id, "attempt": failed_attempt, "backoff": 2})
                            sim_state["stats"]["retries"] += 1
                            w["status"] = "idle"
                            w["job"] = None
                            # Backoff countdown
                            for s in range(2, 0, -1):
                                _emit({"type": "backoff", "job": job_id, "in": s})
                                _sleep(0.5)
                            # Second attempt fails and moves to DLQ
                            _emit({"type": "fail", "job": job_id, "attempt": 2, "backoff": 4})
                            sim_state["stats"]["retries"] += 1
                            sim_state["dlq"].append({"id": job_id})
                            sim_state["stats"]["failed"] += 1
            if done:
                break
            _sleep(0.5)
            ticks += 1
            if ticks > 12:
                break

        with sim_lock:
            sim_state["step"] = "done"
        _emit({"type": "done", "msg": "Simulation complete"})
        with sim_lock:
            sim_state["running"] = False

    @app.route("/simulate")
    def simulate_page():
        return render_template_string(BASE_HTML, content=render_template_string(SIMULATE_BODY))

    @app.route("/api/simulate/start", methods=["POST"])
    def simulate_start():
        payload = request.get_json(silent=True) or {}
        speed = float(payload.get("speed", 1.0))
        jobs = payload.get("jobs") or [
            {"id": "Job-1", "command": "echo Hello World", "max_retries": 3},
            {"id": "Job-2", "command": "python fail_script.py", "max_retries": 2},
        ]
        with sim_lock:
            if sim_state["running"]:
                return jsonify({"status": "already_running"})
            sim_state["speed"] = speed
        t = threading.Thread(target=_run_simulation, args=(jobs,), daemon=True)
        t.start()
        return jsonify({"status": "started"})

    @app.route("/api/simulate/reset", methods=["POST"])
    def simulate_reset():
        with sim_lock:
            sim_state.update({
                "running": False,
                "step": "idle",
                "queue": [],
                "workers": [],
                "dlq": [],
                "logs": [],
                "stats": {"total": 0, "completed": 0, "failed": 0, "retries": 0, "workers": 0},
            })
            # drain event queue
            try:
                while True:
                    sim_events.get_nowait()
            except Exception:
                pass
        return jsonify({"status": "reset"})

    @app.route("/api/simulate/status")
    def simulate_status():
        with sim_lock:
            snapshot = {
                "running": sim_state["running"],
                "step": sim_state["step"],
                "queue": sim_state["queue"],
                "workers": sim_state["workers"],
                "dlq": sim_state["dlq"],
                "stats": sim_state["stats"],
            }
        return jsonify(snapshot)

    @app.route("/api/simulate/stream")
    def simulate_stream():
        def gen():
            # Send initial heartbeat to keep connection alive
            yield "data: {\"type\":\"heartbeat\"}\n\n"
            while True:
                try:
                    evt = sim_events.get(timeout=60)
                except Exception:
                    # periodic heartbeat
                    yield "data: {\"type\":\"heartbeat\"}\n\n"
                    continue
                yield f"data: {__import__('json').dumps(evt)}\n\n"
        headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"}
        return Response(gen(), headers=headers)

    return app
