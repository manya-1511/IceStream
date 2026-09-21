import type { Incident, MetricsSummary, TimeseriesPoint } from "../types";

// Set VITE_API_BASE_URL in frontend/.env if the backend isn't on localhost:8000.
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export const WS_URL: string = API_BASE_URL.replace(/^http/, "ws") + "/ws/metrics";

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${path} responded ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchSummary(): Promise<MetricsSummary> {
  return getJSON<MetricsSummary>("/api/metrics/summary");
}

export function fetchTimeseries(windowMinutes = 10, bucketSeconds = 10): Promise<{ points: TimeseriesPoint[] }> {
  return getJSON(`/api/metrics/timeseries?window_minutes=${windowMinutes}&bucket_seconds=${bucketSeconds}`);
}

export function fetchIncidents(limit = 20): Promise<Incident[]> {
  return getJSON<Incident[]>(`/api/incidents?limit=${limit}`);
}
