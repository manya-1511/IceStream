import type { IncidentStatus, PipelineStatus, Severity } from "../types";

export const statusColor: Record<PipelineStatus, string> = {
  HEALTHY: "var(--color-status-healthy)",
  DEGRADED: "var(--color-status-degraded)",
  QUARANTINED: "var(--color-status-incident)",
  RECOVERING: "var(--color-status-recovering)",
};

export const statusLabel: Record<PipelineStatus, string> = {
  HEALTHY: "Healthy",
  DEGRADED: "Degraded",
  QUARANTINED: "Incident",
  RECOVERING: "Recovering",
};

export const incidentStatusColor: Record<IncidentStatus, string> = {
  ACTIVE: "var(--color-status-incident)",
  RECOVERING: "var(--color-status-recovering)",
  RESOLVED: "var(--color-status-healthy)",
};

export const severityColor: Record<Severity, string> = {
  LOW: "var(--color-status-degraded)",
  MEDIUM: "#fb923c",
  HIGH: "var(--color-status-incident)",
};
