"""
Prometheus metrics for chronoq.

Metrics are defined once here and imported where they're incremented. In
multiprocess mode (Django + Celery workers), each process writes to the shared
PROMETHEUS_MULTIPROC_DIR; Django's /metrics endpoint aggregates across all.

Metric type guide:
- Counter: monotonically increasing (totals; look at rate()).
- Gauge: up/down snapshot of current state.
- Histogram: distributions (for percentiles).
"""

from prometheus_client import Counter, Gauge, Histogram

# --- Counters ---
ticks_total = Counter(
    "chronoq_ticks_total",
    "Scheduler ticks run, labeled by whether this node was leader.",
    ["leader"],
)

executions_total = Counter(
    "chronoq_executions_total",
    "Job executions completed, labeled by final status.",
    ["status"],
)

retries_total = Counter(
    "chronoq_retries_total",
    "Retries scheduled.",
)

circuit_opened_total = Counter(
    "chronoq_circuit_opened_total",
    "Circuit breaker trips (transitions to OPEN), by domain.",
    ["domain"],
)

alerts_total = Counter(
    "chronoq_alerts_total",
    "Alerts fired, by condition.",
    ["condition"],
)

# --- Gauges ---
active_jobs = Gauge(
    "chronoq_active_jobs",
    "Number of active jobs.",
    multiprocess_mode="livesum",
)

# --- Histogram ---
execution_duration_seconds = Histogram(
    "chronoq_execution_duration_seconds",
    "Wall-clock duration of job executions (HTTP call).",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)
