# Dashboard — Day 4

The React frontend is a read-only view over the same tables the streaming
engine (`streaming/`, `monitoring/`) writes to. It never generates or
guesses a number — everything on screen comes from a backend endpoint
backed by a real SQL query (`backend/queries.py`) against
`valid_orders` / `quarantine_orders` / `incidents`.

## Architecture

```text
Postgres (valid_orders, quarantine_orders, incidents)
        |
        v
backend/queries.py          real SQL: counts, bucketed timeseries, incidents
        |
        v
backend/routers/            REST: /api/metrics/summary, /api/metrics/timeseries,
        |                   /api/incidents
        |                   WebSocket: /ws/metrics (a tick every 2s)
        v
frontend/src/hooks/         useLiveMetrics (WS + initial REST fetch),
        |                   useIncidents (polls every 5s)
        v
frontend/src/components/    MetricsRow, PipelineGraph, ChartsRow, IncidentTable
```

The API process and the streaming engine are two separate processes that
only communicate through Postgres — the API has no idea whether a stream
is currently running. It just reports what's actually in the tables right
now. This is why the dashboard works correctly whether you're running
`scripts/demo_incident.py`, `streaming/run_monitored_stream.py`, or nothing
at all (in which case it shows the all-time state and `0` events/sec,
truthfully, rather than a fabricated live number).

## Backend endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/metrics/summary` | The 6 metric cards + overall pipeline status. |
| `GET /api/metrics/timeseries?window_minutes=&bucket_seconds=` | Bucketed history for both line charts. Capped at 300 points regardless of the requested window, so a large window/small bucket combination can't return an unbounded response. |
| `GET /api/incidents?limit=` | Recent incidents, enriched with a real `affected_field` (see below). |
| `WS /ws/metrics` | Pushes `{ summary, point }` every 2 seconds — the same shape as the two REST endpoints above, just so the client doesn't have to poll. |

### How the numbers are computed

- **events/sec** and the **live quality score / error rate**: a 30-second
  rolling window over `checked_at` (when the streaming engine actually
  processed the row — not `invoice_date`, which is the *historical*
  timestamp from 2010–2011). If nothing has been processed in the last 30
  seconds (no stream currently running), the quality score/error rate
  falls back to the all-time totals instead of showing a misleading `0%`.
- **total processed**: `COUNT(valid_orders) + COUNT(quarantine_orders)`, all-time.
- **quarantined**: current `COUNT(quarantine_orders)` — the real backlog.
- **active incidents**: `COUNT(incidents WHERE status != 'RESOLVED')`.
- **status**: `QUARANTINED` if any incident is `ACTIVE`, else `RECOVERING`
  if any is `RECOVERING`, else `DEGRADED` if the last 30s had any invalid
  record, else `HEALTHY`. This deliberately reuses the exact same state
  names as `monitoring/circuit_breaker.py`'s `CircuitState` — the API
  doesn't share memory with a running streaming process's circuit breaker
  (they're different processes), so it re-derives the same state from what's
  actually in the database.
- **affected field** (incidents panel): the most common `rule_triggered`
  among `quarantine_orders` rows in that incident's window (excluding
  `CIRCUIT_OPEN`, which isn't a real quality failure — see
  `docs/ANOMALY_DETECTION.md`), mapped to the real dataset field it
  concerns (e.g. `rule_unit_price_non_negative` → `unit_price`). This is
  genuinely derived from what failed, not a hardcoded label.

### Timeseries bucketing

`get_timeseries()` uses `generate_series` to build every bucket boundary
in the requested window — including ones with zero records — so the chart
shows real gaps (`quality_score: null`) instead of interpolating a fake
100% for a quiet period. The frontend's `RealtimeChart` uses Recharts'
`connectNulls={false}` so those gaps render as gaps, not lines.

## Frontend

Built with Vite + React 19 + TypeScript + Tailwind CSS v4 + Recharts +
lucide-react + `@xyflow/react` (React Flow) — nothing else. No router (a
single page, per the spec), no state-management library (two small hooks
are enough at this scale), no UI kit.

### Live data flow

`useLiveMetrics()` (`src/hooks/useLiveMetrics.ts`):
1. On mount, does one REST call each to `/api/metrics/summary` and
   `/api/metrics/timeseries?window_minutes=10` so the dashboard shows real
   numbers and 10 minutes of real history immediately — not an empty chart
   that only starts filling in after the first WebSocket tick.
2. Opens a WebSocket to `/ws/metrics`. Each tick updates the summary and
   appends the new point to the rolling chart history (replacing the last
   point in place if it's the same bucket, since a bucket keeps updating
   until it closes).
3. Caps history at 60 points (~10 minutes at the default 10s bucket) so
   the chart — and the browser — stay fast no matter how long the page has
   been open.
4. Reconnects automatically 3 seconds after a dropped connection.

`useIncidents()` (`src/hooks/useIncidents.ts`) polls `/api/incidents`
every 5 seconds — simple, and cheap enough at this scale that a WebSocket
for this one list wasn't worth the added complexity.

### Component structure

```text
App.tsx                    thin composition only — no page logic lives here
├── Header                 brand + live/reconnecting indicator + status badge
├── MetricsRow              → 6x MetricCard
├── Panel("Live Pipeline")  → PipelineGraph (React Flow)
│                              └── PipelineNode (custom node renderer)
├── ChartsRow                → 2x Panel → RealtimeChart (Recharts)
└── Panel("Recent Incidents") → IncidentTable → IncidentRow(s)
```

`StatusBadge` (colored dot + label) is shared by the header, and
`IncidentRow`. `Panel` (border + surface + optional title) is shared by
the pipeline, both charts, and the incidents table, so the visual
language stays consistent without repeating className strings everywhere.

### Pipeline diagram node coloring

`PipelineGraph` maps the summary's `status` onto the QUALITY and
POSTGRESQL nodes' color (green/amber/red/indigo, matching
HEALTHY/DEGRADED/QUARANTINED/RECOVERING). The QUARANTINE node is
highlighted red only when `quarantined_count > 0`. The REAL DATA and
STREAM nodes are always shown in the neutral brand color — this project
doesn't monitor the streaming *process* itself (only the data flowing
through it), so coloring them green would be asserting something we don't
actually measure.

### Design

Dark "ink" palette (`#0B1120` base, not pure black) with a single cyan
brand accent (`#4FD8E8`) reserved for interactive/brand elements, and a
separate 4-color functional palette for pipeline/incident status that's
never reused decoratively. IBM Plex Sans for UI text, IBM Plex Mono with
tabular figures for every number that updates live (event counts, metric
values, timestamps) so digits don't jitter width as they change — a real
convention borrowed from tools like Grafana/Datadog, not decoration.

No gradients. Motion is limited to one thing: a pulsing dot on the live
status badge, which is the one place "this is live" actually needs to be
communicated. Chart line animation is disabled (`isAnimationActive={false}`)
so updates feel immediate rather than performing a re-entrance animation
on every tick.

## Try it

Terminal 1:
```bash
cd backend && uvicorn main:app --reload --port 8000
```

Terminal 2:
```bash
cd frontend && npm install && npm run dev
```

Terminal 3 (generates real activity to watch live):
```bash
python scripts/demo_incident.py
```

Open http://localhost:5173 — you'll see the metric cards update, the
pipeline diagram's QUALITY/POSTGRESQL nodes turn red and the QUARANTINE
node light up as the demo's injected fault trips an incident, then
everything return to green as recovery completes, all from the same demo
run described in `docs/ANOMALY_DETECTION.md`.

See `docs/SETUP.md` for full step-by-step instructions.
