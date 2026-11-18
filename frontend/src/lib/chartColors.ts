/**
 * Shared restrained chart palette mapped directly to Groundwork design tokens
 * (docs/design-system.md section 3 & section 7). Every metric uses one
 * consistent colour across all Diagnostics charts.
 */
export const CHART_COLORS = {
  volume: "#526B89", // --color-accent (muted slate-blue)
  first_response: "#202A35", // --color-ink
  p90_first_response: "#A96F2C", // --color-warning
  triage_time: "#526B89", // --color-accent
  resolution_time: "#267A59", // --color-success
  backlog: "#A96F2C", // --color-warning
  workload: "#526B89", // --color-accent
  reassignment: "#B84D49", // --color-danger
  grid: "#E7E9E8", // --color-border
  axis: "#687482", // --color-muted
} as const;

export type MetricColorKey = keyof typeof CHART_COLORS;
