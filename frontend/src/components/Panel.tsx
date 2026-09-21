import type { ReactNode } from "react";

interface PanelProps {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Panel({ title, action, children, className = "", bodyClassName = "" }: PanelProps) {
  return (
    <section className={`rounded-lg border border-ink-600 bg-ink-800 ${className}`}>
      {title && (
        <header className="flex items-center justify-between border-b border-ink-600 px-4 py-3">
          <h2 className="text-sm font-medium text-ink-100">{title}</h2>
          {action}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
