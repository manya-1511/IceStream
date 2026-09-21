// Mirrors backend/schemas.py — kept in sync by hand since this is a small
// project; see docs/DASHBOARD.md if these ever drift from the API.

export type PipelineStatus = "HEALTHY" | "DEGRADED" | "QUARANTINED" | "RECOVERING";

export interface MetricsSummary {
  events_per_sec: number;
  total_processed: number;
  quality_score: number;
  error_rate: number;
  quarantined_count: number;
  active_incidents: number;
  status: PipelineStatus;
}

export interface TimeseriesPoint {
  timestamp: string;
  events_per_sec: number;
  quality_score: number | null;
}

export type IncidentType = "ERROR_RATE" | "VOLUME";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type IncidentStatus = "ACTIVE" | "RECOVERING" | "RESOLVED";

export interface Incident {
  incident_id: number;
  started_at: string;
  resolved_at: string | null;
  type: IncidentType;
  severity: Severity;
  error_rate: number | null;
  description: string;
  status: IncidentStatus;
  affected_field: string | null;
}

export interface WebSocketTick {
  summary: MetricsSummary;
  point: TimeseriesPoint;
}
