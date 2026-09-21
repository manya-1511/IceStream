import { ShieldCheck } from "lucide-react";
import { IncidentRow } from "./IncidentRow";
import type { Incident } from "../types";

interface IncidentTableProps {
  incidents: Incident[];
}

const columns = ["ID", "Incident", "Error Rate", "Severity", "Affected Field", "Detected", "Status"];

export function IncidentTable({ incidents }: IncidentTableProps) {
  if (incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
        <ShieldCheck size={22} className="text-status-healthy" style={{ color: "var(--color-status-healthy)" }} />
        <p className="text-sm text-ink-100">No incidents recorded</p>
        <p className="text-xs text-ink-300">The pipeline hasn't crossed the error-rate or volume threshold.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-ink-600">
            {columns.map((col) => (
              <th key={col} className="whitespace-nowrap px-4 py-2.5 text-xs font-medium text-ink-300">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {incidents.map((incident) => (
            <IncidentRow key={incident.incident_id} incident={incident} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
