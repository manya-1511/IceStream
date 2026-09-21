export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatPercent(value: number): string {
  return value.toFixed(1);
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString("en-US", { hour12: false });
}

export function formatClock(iso: string): string {
  // Short label for chart X axes — HH:MM:SS
  return formatTime(iso);
}
