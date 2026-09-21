import { useMemo } from "react";
import { Background, BackgroundVariant, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Archive, Database, Filter, Radio, Waves } from "lucide-react";
import { PipelineNode, type NodeTone, type PipelineNodeData } from "./PipelineNode";
import type { MetricsSummary } from "../types";

const nodeTypes = { pipelineNode: PipelineNode };

interface PipelineGraphProps {
  summary: MetricsSummary | null;
}

function toneForStatus(status: MetricsSummary["status"] | undefined): NodeTone {
  switch (status) {
    case "HEALTHY":
      return "healthy";
    case "DEGRADED":
      return "degraded";
    case "QUARANTINED":
      return "incident";
    case "RECOVERING":
      return "recovering";
    default:
      return "neutral";
  }
}

function toneColorFor(tone: NodeTone): string {
  const map: Record<NodeTone, string> = {
    neutral: "var(--color-ice)",
    healthy: "var(--color-status-healthy)",
    degraded: "var(--color-status-degraded)",
    incident: "var(--color-status-incident)",
    recovering: "var(--color-status-recovering)",
  };
  return map[tone];
}

function edgeStyle(color: string, animated = false) {
  return {
    animated,
    style: { stroke: color, strokeWidth: 1.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
  };
}

export function PipelineGraph({ summary }: PipelineGraphProps) {
  const pipelineTone = toneForStatus(summary?.status);
  const quarantineTone: NodeTone = summary && summary.quarantined_count > 0 ? "incident" : "neutral";

  const nodes = useMemo<Node<PipelineNodeData>[]>(
    () => [
      {
        id: "source",
        type: "pipelineNode",
        position: { x: 0, y: 70 },
        data: {
          label: "REAL DATA",
          sublabel: "Online Retail II",
          icon: Waves,
          tone: "neutral",
          handles: { right: true },
        },
      },
      {
        id: "stream",
        type: "pipelineNode",
        position: { x: 210, y: 70 },
        data: {
          label: "STREAM",
          sublabel: `${summary ? summary.events_per_sec.toFixed(1) : "—"} rec/s`,
          icon: Radio,
          tone: "neutral",
          handles: { left: true, right: true },
        },
      },
      {
        id: "quality",
        type: "pipelineNode",
        position: { x: 420, y: 70 },
        data: {
          label: "QUALITY",
          sublabel: summary ? `${summary.quality_score.toFixed(1)}% score` : "—",
          icon: Filter,
          tone: pipelineTone,
          handles: { left: true, right: true, bottom: true },
        },
      },
      {
        id: "database",
        type: "pipelineNode",
        position: { x: 630, y: 70 },
        data: {
          label: "POSTGRESQL",
          sublabel: summary ? `${summary.total_processed.toLocaleString()} rows` : "—",
          icon: Database,
          tone: pipelineTone,
          handles: { left: true },
        },
      },
      {
        id: "quarantine",
        type: "pipelineNode",
        position: { x: 420, y: 190 },
        data: {
          label: "QUARANTINE",
          sublabel: summary ? `${summary.quarantined_count.toLocaleString()} held` : "—",
          icon: Archive,
          tone: quarantineTone,
          handles: { top: true },
        },
      },
    ],
    [summary, pipelineTone, quarantineTone],
  );

  const edges = useMemo<Edge[]>(
    () => [
      { id: "e-source-stream", source: "source", target: "stream", ...edgeStyle("var(--color-ink-500)") },
      { id: "e-stream-quality", source: "stream", target: "quality", ...edgeStyle("var(--color-ink-500)") },
      {
        id: "e-quality-database",
        source: "quality",
        target: "database",
        ...edgeStyle(toneColorFor(pipelineTone)),
      },
      {
        id: "e-quality-quarantine",
        source: "quality",
        target: "quarantine",
        ...edgeStyle(toneColorFor(quarantineTone), quarantineTone === "incident"),
      },
    ],
    [pipelineTone, quarantineTone],
  );

  return (
    <div className="h-[300px] w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        panOnScroll={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
      >
        <Background variant={BackgroundVariant.Dots} color="var(--color-ink-700)" gap={20} size={1} />
      </ReactFlow>
    </div>
  );
}
