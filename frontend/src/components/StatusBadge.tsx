interface StatusBadgeProps {
  color: string;
  label: string;
  pulse?: boolean;
  size?: "sm" | "md";
}

export function StatusBadge({ color, label, pulse = false, size = "md" }: StatusBadgeProps) {
  const dotSize = size === "sm" ? "size-1.5" : "size-2";
  const textSize = size === "sm" ? "text-xs" : "text-sm";

  return (
    <span className={`inline-flex items-center gap-2 font-mono ${textSize} text-ink-100`}>
      <span
        className={`${dotSize} rounded-full ${pulse ? "animate-pulse-dot" : ""}`}
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}
