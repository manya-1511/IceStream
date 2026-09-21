import { StatusBadge } from "./StatusBadge";
import { incidentStatusColor, severityColor } from "../lib/status";
import { formatTime } from "../lib/format";
import type { Incident } from "../types";

function incidentCode(id: number): string {
  return `INC-${String(id).padStart(3, "0")}`;
}

function titleFor(incident: Incident): string {
  return incident.type === "ERROR_RATE" ? "High error rate" : "Unusual volume spike";
}

interface IncidentRowProps {
  incident: Incident;
}

export function IncidentRow({ incident }: IncidentRowProps) {
  return (
    <tr className="border-b border-ink-700 last:border-0">
      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ice">{incidentCode(incident.incident_id)}</td>
      <td className="px-4 py-3">
        <div className="text-sm text-ink-50">{titleFor(incident)}</div>
        <div className="mt-0.5 truncate text-xs text-ink-300" title={incident.description}>
          {incident.description}
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3 font-mono text-sm tabular-nums text-ink-50">
        {incident.error_rate !== null ? `${incident.error_rate.toFixed(1)}%` : "—"}
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        <span
          className="rounded px-1.5 py-0.5 font-mono text-[11px] font-medium"
          style={{
            color: severityColor[incident.severity],
            backgroundColor: `color-mix(in srgb, ${severityColor[incident.severity]} 16%, transparent)`,
          }}
        >
          {incident.severity}
        </span>
      </td>
      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-300">
        {incident.affected_field ?? "—"}
      </td>
      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-300">{formatTime(incident.started_at)}</td>
      <td className="whitespace-nowrap px-4 py-3">
        <StatusBadge color={incidentStatusColor[incident.status]} label={incident.status} size="sm" />
      </td>
    </tr>
  );
}
