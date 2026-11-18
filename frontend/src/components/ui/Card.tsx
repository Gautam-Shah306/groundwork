import type { ReactNode } from "react";

export interface CardProps {
  title?: string;
  description?: string;
  headerAction?: ReactNode;
  children: ReactNode;
  className?: string;
  elevated?: boolean;
}

export function Card({
  title,
  description,
  headerAction,
  children,
  className = "",
  elevated = false,
}: CardProps) {
  return (
    <section
      className={[
        "rounded-card border border-border bg-surface p-5",
        elevated ? "shadow-subtle" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {(title || description || headerAction) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            {title && (
              <h2 className="text-[14px] font-semibold leading-snug text-ink">
                {title}
              </h2>
            )}
            {description && (
              <p className="mt-1 text-[12px] leading-relaxed text-muted">
                {description}
              </p>
            )}
          </div>
          {headerAction && <div className="shrink-0">{headerAction}</div>}
        </header>
      )}
      <div>{children}</div>
    </section>
  );
}
