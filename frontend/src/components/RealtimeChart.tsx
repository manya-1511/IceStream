import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatClock } from "../lib/format";
import type { TimeseriesPoint } from "../types";

interface RealtimeChartProps {
  data: TimeseriesPoint[];
  dataKey: "events_per_sec" | "quality_score";
  color: string;
  unit?: string;
  yDomain?: [number, number];
}

interface TooltipPayloadItem {
  value: number | null;
}

function ChartTooltip({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
  unit?: string;
}) {
  if (!active || !payload?.length || payload[0].value === null) return null;
  return (
    <div className="rounded-md border border-ink-600 bg-ink-900 px-2.5 py-1.5 font-mono text-xs text-ink-50 shadow-lg">
      <div className="text-ink-300">{label ? formatClock(label) : ""}</div>
      <div className="mt-0.5 font-semibold">
        {payload[0].value}
        {unit}
      </div>
    </div>
  );
}

export function RealtimeChart({ data, dataKey, color, unit = "", yDomain }: RealtimeChartProps) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
        <CartesianGrid stroke="var(--color-ink-700)" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="timestamp"
          tickFormatter={formatClock}
          stroke="var(--color-ink-600)"
          tick={{ fill: "var(--color-ink-300)", fontSize: 11, fontFamily: "var(--font-mono)" }}
          tickLine={false}
          axisLine={false}
          minTickGap={40}
        />
        <YAxis
          domain={yDomain ?? ["auto", "auto"]}
          stroke="var(--color-ink-600)"
          tick={{ fill: "var(--color-ink-300)", fontSize: 11, fontFamily: "var(--font-mono)" }}
          tickLine={false}
          axisLine={false}
          width={40}
        />
        <Tooltip content={<ChartTooltip unit={unit} />} />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
          connectNulls={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
