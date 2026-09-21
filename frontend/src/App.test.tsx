import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { Incident, MetricsSummary, TimeseriesPoint } from "./types";

const summary: MetricsSummary = {
  events_per_sec: 12.4,
  total_processed: 4820,
  quality_score: 97.3,
  error_rate: 2.7,
  quarantined_count: 6,
  active_incidents: 1,
  status: "DEGRADED",
};

const points: TimeseriesPoint[] = [
  { timestamp: "2026-01-01T00:00:00", events_per_sec: 10, quality_score: 98 },
  { timestamp: "2026-01-01T00:00:10", events_per_sec: 12, quality_score: 97 },
];

const incidents: Incident[] = [
  {
    incident_id: 1,
    started_at: "2026-01-01T00:00:00",
    resolved_at: null,
    type: "ERROR_RATE",
    severity: "MEDIUM",
    error_rate: 17.2,
    description: "error_rate 17.2% exceeded threshold 5.0%",
    status: "ACTIVE",
    affected_field: "unit_price",
  },
];

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/metrics/summary")) {
          return Promise.resolve(new Response(JSON.stringify(summary)));
        }
        if (url.includes("/api/metrics/timeseries")) {
          return Promise.resolve(new Response(JSON.stringify({ points })));
        }
        if (url.includes("/api/incidents")) {
          return Promise.resolve(new Response(JSON.stringify(incidents)));
        }
        return Promise.reject(new Error(`unexpected fetch: ${url}`));
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the brand, metric cards, pipeline, charts, and incidents without throwing", async () => {
    render(<App />);

    expect(screen.getByText("ICESTREAM")).toBeInTheDocument();
    expect(screen.getByText("Events/sec")).toBeInTheDocument();
    expect(screen.getByText("Live Pipeline")).toBeInTheDocument();
    expect(screen.getByText("Event Throughput")).toBeInTheDocument();
    expect(screen.getByText("Data Quality")).toBeInTheDocument();
    expect(screen.getByText("Recent Incidents")).toBeInTheDocument();

    // Real values from the mocked API should reach the DOM, not placeholders.
    await waitFor(() => expect(screen.getByText("97.3")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("INC-001")).toBeInTheDocument());
    expect(screen.getByText("unit_price")).toBeInTheDocument();
  });

  it("shows the empty state when there are no incidents", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/api/incidents")) {
          return Promise.resolve(new Response(JSON.stringify([])));
        }
        if (url.includes("/api/metrics/summary")) {
          return Promise.resolve(new Response(JSON.stringify(summary)));
        }
        return Promise.resolve(new Response(JSON.stringify({ points: [] })));
      }),
    );

    render(<App />);
    await waitFor(() => expect(screen.getByText("No incidents recorded")).toBeInTheDocument());
  });
});
