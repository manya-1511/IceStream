import { Snowflake, Wifi, WifiOff } from "lucide-react";
import { StatusBadge } from "./StatusBadge";
import { statusColor, statusLabel } from "../lib/status";
import type { MetricsSummary } from "../types";

interface HeaderProps {
  status: MetricsSummary["status"] | null;
  connected: boolean;
}

export function Header({ status, connected }: HeaderProps) {
  return (
    <header className="flex flex-col gap-3 border-b border-ink-600 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
      <div className="flex items-center gap-2.5">
        <Snowflake size={20} style={{ color: "var(--color-ice)" }} strokeWidth={2.25} />
        <div>
          <h1 className="text-sm font-semibold tracking-wide text-ink-50">ICESTREAM</h1>
          <p className="text-xs text-ink-300">Real-Time Data Observability</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1.5 font-mono text-xs text-ink-300">
          {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
          {connected ? "live" : "reconnecting…"}
        </span>
        {status && <StatusBadge color={statusColor[status]} label={statusLabel[status]} pulse />}
      </div>
    </header>
  );
}
