import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Briefcase,
  Compass,
  FlaskConical,
  LayoutDashboard,
  TrendingUp,
} from "lucide-react";

export type NavGroupId = "workspace" | "stages";

export interface NavItemConfig {
  id: string;
  label: string;
  path: string;
  group: NavGroupId;
  groupLabel: string;
  eyebrow: string;
  emptyTitle: string;
  emptyDescription: string;
  icon: LucideIcon;
}

export const NAV_GROUPS: Array<{ id: NavGroupId; label: string }> = [
  { id: "workspace", label: "Workspace" },
  { id: "stages", label: "Stages" },
];

export const NAV_ITEMS: NavItemConfig[] = [
  {
    id: "overview",
    label: "Overview",
    path: "/",
    group: "workspace",
    groupLabel: "Workspace",
    eyebrow: "Workspace",
    emptyTitle: "No active engagement loaded",
    emptyDescription:
      "Select or seed a synthetic engagement to view the current problem statement, stage progress, key findings, and next actions.",
    icon: LayoutDashboard,
  },
  {
    id: "engagements",
    label: "Engagements",
    path: "/engagements",
    group: "workspace",
    groupLabel: "Workspace",
    eyebrow: "Workspace",
    emptyTitle: "No engagements created yet",
    emptyDescription:
      "Client engagements and their synthetic demonstration datasets will be listed here once created below or seeded via the backend CLI.",
    icon: Briefcase,
  },
  {
    id: "discovery",
    label: "Discovery",
    path: "/discovery",
    group: "stages",
    groupLabel: "Stages",
    eyebrow: "Stage 01 · Discover",
    emptyTitle: "No discovery notes captured",
    emptyDescription:
      "Add client statements, interview notes, confirmed facts, unknowns, and follow-up questions to structure a testable problem brief.",
    icon: Compass,
  },
  {
    id: "diagnostics",
    label: "Diagnostics",
    path: "/diagnostics",
    group: "stages",
    groupLabel: "Stages",
    eyebrow: "Stage 02 · Diagnose",
    emptyTitle: "No engagement selected",
    emptyDescription:
      "Select or create an engagement in Workspace before uploading and validating a support-ticket CSV dataset.",
    icon: Activity,
  },
  {
    id: "prototypes",
    label: "Prototypes",
    path: "/prototypes",
    group: "stages",
    groupLabel: "Stages",
    eyebrow: "Stage 03 · Build",
    emptyTitle: "No triage proposals awaiting review",
    emptyDescription:
      "Run the support triage workflow to review agent categorisations, policy-grounded draft responses, and human approval history.",
    icon: FlaskConical,
  },
  {
    id: "outcomes",
    label: "Outcomes",
    path: "/outcomes",
    group: "stages",
    groupLabel: "Stages",
    eyebrow: "Stage 04 · Measure",
    emptyTitle: "No outcome comparison recorded",
    emptyDescription:
      "Define KPI baselines, sourced targets, and clearly labelled simulated pilot comparisons to evaluate whether an intervention worked.",
    icon: TrendingUp,
  },
];

export function findNavItemByPath(pathname: string): NavItemConfig | undefined {
  if (pathname === "/") {
    return NAV_ITEMS[0];
  }
  return NAV_ITEMS.find(
    (item) => item.path !== "/" && pathname.startsWith(item.path)
  );
}
