import { Handle, Position } from "@xyflow/react";
import type { LucideIcon } from "lucide-react";

export type NodeTone = "neutral" | "healthy" | "degraded" | "incident" | "recovering";

const toneColor: Record<NodeTone, string> = {
  neutral: "var(--color-ice)",
  healthy: "var(--color-status-healthy)",
  degraded: "var(--color-status-degraded)",
  incident: "var(--color-status-incident)",
  recovering: "var(--color-status-recovering)",
};

export interface PipelineNodeData {
  label: string;
  sublabel: string;
  icon: LucideIcon;
  tone: NodeTone;
  handles?: { top?: boolean; bottom?: boolean; left?: boolean; right?: boolean };
  [key: string]: unknown;
}

export function PipelineNode({ data }: { data: PipelineNodeData }) {
  const Icon = data.icon;
  const color = toneColor[data.tone];
  const handles = data.handles ?? { left: true, right: true };

  return (
    <div
      className="flex w-[168px] items-center gap-2.5 rounded-lg border bg-ink-800 px-3 py-2.5"
      style={{ borderColor: color }}
    >
      {handles.left && <Handle type="target" position={Position.Left} style={{ background: color, border: "none" }} />}
      {handles.top && <Handle type="target" position={Position.Top} style={{ background: color, border: "none" }} />}

      <div
        className="flex size-8 shrink-0 items-center justify-center rounded-md"
        style={{ backgroundColor: `color-mix(in srgb, ${color} 18%, transparent)` }}
      >
        <Icon size={16} style={{ color }} />
      </div>
      <div className="min-w-0">
        <div className="truncate text-xs font-semibold text-ink-50">{data.label}</div>
        <div className="truncate font-mono text-[10.5px] text-ink-300">{data.sublabel}</div>
      </div>

      {handles.right && (
        <Handle type="source" position={Position.Right} style={{ background: color, border: "none" }} />
      )}
      {handles.bottom && (
        <Handle type="source" position={Position.Bottom} style={{ background: color, border: "none" }} />
      )}
    </div>
  );
}
