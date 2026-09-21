import { Panel } from "./Panel";
import { RealtimeChart } from "./RealtimeChart";
import type { TimeseriesPoint } from "../types";

interface ChartsRowProps {
  points: TimeseriesPoint[];
}

export function ChartsRow({ points }: ChartsRowProps) {
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <Panel title="Event Throughput" bodyClassName="p-3">
        <RealtimeChart data={points} dataKey="events_per_sec" color="var(--color-ice)" unit="/s" />
      </Panel>
      <Panel title="Data Quality" bodyClassName="p-3">
        <RealtimeChart
          data={points}
          dataKey="quality_score"
          color="var(--color-status-healthy)"
          unit="%"
          yDomain={[0, 100]}
        />
      </Panel>
    </div>
  );
}
