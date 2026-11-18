import { EmptyState, Eyebrow } from "../components/ui";
import type { NavItemConfig } from "../lib/navigation";

export interface StagePlaceholderPageProps {
  item: NavItemConfig;
}

export function StagePlaceholderPage({ item }: StagePlaceholderPageProps) {
  const Icon = item.icon;

  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <Eyebrow>{item.eyebrow}</Eyebrow>
        <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
          {item.label}
        </h1>
      </header>

      <EmptyState
        eyebrow="Synthetic workspace"
        title={item.emptyTitle}
        description={item.emptyDescription}
        icon={<Icon size={16} strokeWidth={1.75} aria-hidden="true" />}
      />
    </div>
  );
}
