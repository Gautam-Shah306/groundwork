import { NavLink } from "react-router-dom";
import { Settings } from "lucide-react";
import { NAV_GROUPS, NAV_ITEMS } from "../../lib/navigation";

export interface SidebarProps {
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <aside className="flex h-full w-[var(--sidebar-width)] shrink-0 flex-col border-r border-border bg-surface-subtle">
      {/* Brand header */}
      <div className="border-b border-border px-5 py-5">
        <div className="font-display text-[26px] font-normal leading-none tracking-tight text-ink">
          Groundwork
        </div>
        <div className="mt-1.5 font-sans text-[9px] font-bold uppercase tracking-[0.12em] text-muted">
          BUSINESS OPERATIONS INTELLIGENCE
        </div>
      </div>

      {/* Primary grouped navigation */}
      <nav
        aria-label="Primary navigation"
        className="flex-1 overflow-y-auto px-3 py-5"
      >
        <div className="space-y-6">
          {NAV_GROUPS.map((group) => {
            const items = NAV_ITEMS.filter((item) => item.group === group.id);
            return (
              <div key={group.id} role="group" aria-label={group.label}>
                <div className="mb-2 px-2.5 font-sans text-[9px] font-bold uppercase tracking-[0.12em] text-muted">
                  {group.label}
                </div>
                <ul className="space-y-0.5">
                  {items.map((item) => {
                    const Icon = item.icon;
                    return (
                      <li key={item.id}>
                        <NavLink
                          to={item.path}
                          end={item.path === "/"}
                          onClick={onNavigate}
                          className={({ isActive }) =>
                            [
                              "flex items-center gap-2.5 rounded-control px-2.5 py-2 text-[13px] transition-colors",
                              "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                              isActive
                                ? "bg-accent-soft font-semibold text-ink"
                                : "font-medium text-muted hover:bg-surface hover:text-ink",
                            ].join(" ")
                          }
                        >
                          {({ isActive }) => (
                            <>
                              <Icon
                                size={16}
                                strokeWidth={1.75}
                                aria-hidden="true"
                                className={isActive ? "text-accent" : "text-muted"}
                              />
                              <span>{item.label}</span>
                            </>
                          )}
                        </NavLink>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      </nav>

      {/* Anchored bottom settings & user block */}
      <div className="border-t border-border px-3 py-3 space-y-2">
        <button
          type="button"
          disabled
          aria-disabled="true"
          title="Settings are not enabled in this milestone"
          className="flex w-full cursor-not-allowed items-center gap-2.5 rounded-control px-2.5 py-2 text-[13px] font-medium text-muted/70"
        >
          <Settings size={16} strokeWidth={1.75} aria-hidden="true" />
          <span>Settings</span>
        </button>

        <div className="flex items-center gap-2.5 rounded-control border border-border bg-surface px-2.5 py-2">
          <div
            aria-hidden="true"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent"
          >
            DO
          </div>
          <div className="min-w-0">
            <div className="truncate text-[12px] font-semibold text-ink">
              Demo operator
            </div>
            <div className="truncate text-[11px] text-muted">
              Synthetic workspace
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
