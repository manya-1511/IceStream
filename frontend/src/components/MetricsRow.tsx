import { Activity, AlertTriangle, Archive, CheckCircle2, Database, Siren } from "lucide-react";
import { MetricCard } from "./MetricCard";
import { formatNumber, formatPercent } from "../lib/format";
import type { MetricsSummary } from "../types";

interface MetricsRowProps {
  summary: MetricsSummary | null;
}

export function MetricsRow({ summary }: MetricsRowProps) {
  const events = summary ? formatPercent(summary.events_per_sec) : "—";
  const total = summary ? formatNumber(summary.total_processed) : "—";
  const quality = summary ? formatPercent(summary.quality_score) : "—";
  const errorRate = summary ? formatPercent(summary.error_rate) : "—";
  const quarantined = summary ? formatNumber(summary.quarantined_count) : "—";
  const incidents = summary ? formatNumber(summary.active_incidents) : "—";

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <MetricCard label="Events/sec" value={events} icon={Activity} tone="neutral" />
      <MetricCard label="Total Processed" value={total} icon={Database} tone="neutral" />
      <MetricCard
        label="Quality Score"
        value={quality}
        unit="%"
        icon={CheckCircle2}
        tone={summary && summary.quality_score < 95 ? "warn" : "good"}
      />
      <MetricCard
        label="Error Rate"
        value={errorRate}
        unit="%"
        icon={AlertTriangle}
        tone={summary && summary.error_rate > 5 ? "bad" : "neutral"}
      />
      <MetricCard
        label="Quarantined"
        value={quarantined}
        icon={Archive}
        tone={summary && summary.quarantined_count > 0 ? "warn" : "neutral"}
      />
      <MetricCard
        label="Active Incidents"
        value={incidents}
        icon={Siren}
        tone={summary && summary.active_incidents > 0 ? "bad" : "good"}
      />
    </div>
  );
}
