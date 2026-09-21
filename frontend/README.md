# IceStream Dashboard

React + TypeScript + Tailwind CSS v4 + Recharts + lucide-react + React Flow
(`@xyflow/react`). A single-page, read-only view over the real pipeline
state in Postgres — see [`docs/DASHBOARD.md`](../docs/DASHBOARD.md) for the
full design and data-flow write-up.

## Setup

```bash
npm install
cp .env.example .env   # only needed if the API isn't on http://localhost:8000
npm run dev
```

Requires the backend running (`cd ../backend && uvicorn main:app --reload --port 8000`)
and Postgres with at least the Day 1-3 schema applied — see the project
root's [`docs/SETUP.md`](../docs/SETUP.md).

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Start the dev server at http://localhost:5173 |
| `npm run build` | Type-check (`tsc -b`) and build for production into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run test` | Run the component smoke test (Vitest + Testing Library + jsdom) |
| `npm run lint` | Run oxlint |

## Structure

```text
src/
├── App.tsx              thin composition only
├── types.ts              mirrors backend/schemas.py
├── lib/
│   ├── api.ts            fetch helpers + WebSocket URL
│   ├── format.ts         number/time formatting
│   └── status.ts         status -> color/label maps
├── hooks/
│   ├── useLiveMetrics.ts  WebSocket + rolling chart history
│   └── useIncidents.ts    polls /api/incidents
└── components/
    ├── Header.tsx
    ├── MetricCard.tsx / MetricsRow.tsx
    ├── PipelineNode.tsx / PipelineGraph.tsx   (React Flow)
    ├── RealtimeChart.tsx / ChartsRow.tsx       (Recharts)
    ├── IncidentRow.tsx / IncidentTable.tsx
    ├── StatusBadge.tsx    shared colored-dot badge
    └── Panel.tsx          shared card/section chrome
```
