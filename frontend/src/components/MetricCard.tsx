import type { LucideIcon } from "lucide-react";

type Tone = "neutral" | "good" | "warn" | "bad";

const toneColor: Record<Tone, string> = {
  neutral: "var(--color-ice)",
  good: "var(--color-status-healthy)",
  warn: "var(--color-status-degraded)",
  bad: "var(--color-status-incident)",
};

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  icon: LucideIcon;
  tone?: Tone;
}

export function MetricCard({ label, value, unit, icon: Icon, tone = "neutral" }: MetricCardProps) {
  const color = toneColor[tone];

  return (
    <div className="rounded-lg border border-ink-600 bg-ink-800 px-4 py-3.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium tracking-wide text-ink-300">{label}</span>
        <Icon size={15} strokeWidth={2} style={{ color }} />
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className="font-mono text-2xl font-semibold tabular-nums text-ink-50">{value}</span>
        {unit && <span className="font-mono text-sm text-ink-300">{unit}</span>}
      </div>
    </div>
  );
}
