import { Header } from "./components/Header";
import { MetricsRow } from "./components/MetricsRow";
import { ChartsRow } from "./components/ChartsRow";
import { Panel } from "./components/Panel";
import { PipelineGraph } from "./components/PipelineGraph";
import { IncidentTable } from "./components/IncidentTable";
import { useLiveMetrics } from "./hooks/useLiveMetrics";
import { useIncidents } from "./hooks/useIncidents";

export default function App() {
  const { summary, points, connected } = useLiveMetrics();
  const incidents = useIncidents();

  return (
    <div className="min-h-screen bg-ink-950">
      <Header status={summary?.status ?? null} connected={connected} />

      <main className="mx-auto flex max-w-[1440px] flex-col gap-3 px-5 py-5 sm:px-8">
        <MetricsRow summary={summary} />

        <Panel title="Live Pipeline">
          <PipelineGraph summary={summary} />
        </Panel>

        <ChartsRow points={points} />

        <Panel title="Recent Incidents">
          <IncidentTable incidents={incidents} />
        </Panel>
      </main>
    </div>
  );
}
