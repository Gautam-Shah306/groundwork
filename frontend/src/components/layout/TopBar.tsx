import { useState } from "react";
import { useLocation } from "react-router-dom";
import { ChevronRight, HelpCircle, Menu } from "lucide-react";
import { useEngagement } from "../../context/EngagementContext";
import { findNavItemByPath } from "../../lib/navigation";
import { SystemStatus } from "./SystemStatus";

export interface TopBarProps {
  onToggleMobileNav?: () => void;
}

export function TopBar({ onToggleMobileNav }: TopBarProps) {
  const { pathname } = useLocation();
  const { activeEngagement } = useEngagement();
  const [helpOpen, setHelpOpen] = useState(false);

  const activeNav = findNavItemByPath(pathname);
  const isDevRoute = pathname.startsWith("/dev/components");

  const crumbs = isDevRoute
    ? ["Groundwork", "Developer", "Components"]
    : activeNav
      ? [
          "Groundwork",
          ...(activeEngagement ? [activeEngagement.name] : []),
          activeNav.groupLabel,
          activeNav.label,
        ]
      : ["Groundwork", "Workspace"];

  return (
    <header className="relative flex h-[var(--topbar-height)] shrink-0 items-center justify-between gap-4 border-b border-border bg-surface px-5 lg:px-10">
      <div className="flex min-w-0 items-center gap-3">
        {onToggleMobileNav && (
          <button
            type="button"
            onClick={onToggleMobileNav}
            aria-label="Toggle navigation menu"
            className="inline-flex h-8 w-8 items-center justify-center rounded-control border border-border bg-surface text-ink hover:bg-surface-subtle lg:hidden focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <Menu size={16} strokeWidth={1.75} aria-hidden="true" />
          </button>
        )}

        <nav aria-label="Breadcrumb" className="min-w-0">
          <ol className="flex flex-wrap items-center gap-1.5 text-[12px]">
            {crumbs.map((crumb, index) => {
              const isLast = index === crumbs.length - 1;
              return (
                <li key={`${crumb}-${index}`} className="flex items-center gap-1.5 min-w-0">
                  {index > 0 && (
                    <ChevronRight
                      size={14}
                      strokeWidth={1.75}
                      aria-hidden="true"
                      className="shrink-0 text-muted/70"
                    />
                  )}
                  <span
                    aria-current={isLast ? "page" : undefined}
                    className={
                      isLast
                        ? "truncate font-semibold text-ink"
                        : "truncate font-medium text-muted"
                    }
                  >
                    {crumb}
                  </span>
                </li>
              );
            })}
          </ol>
        </nav>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        <SystemStatus />

        <div className="relative">
          <button
            type="button"
            aria-expanded={helpOpen}
            aria-label="Workspace help"
            onClick={() => setHelpOpen((prev) => !prev)}
            className="inline-flex h-8 items-center gap-1.5 rounded-control border border-border bg-surface px-2.5 text-[12px] font-medium text-ink hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <HelpCircle size={16} strokeWidth={1.75} aria-hidden="true" />
            <span>Help</span>
          </button>

          {helpOpen && (
            <div
              role="dialog"
              aria-label="Groundwork workspace help"
              className="absolute right-0 top-10 z-30 w-72 rounded-card border border-border bg-surface p-4 shadow-subtle"
            >
              <div className="text-[12px] font-semibold text-ink">
                Groundwork Workspace
              </div>
              <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
                Work sequentially through Discover, Diagnose, Build, and
                Measure. All demonstration data is synthetic, and human approval
                is required before any action is recorded.
              </p>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
