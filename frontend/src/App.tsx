import { lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { EmptyState, Eyebrow } from "./components/ui";
import { EngagementProvider } from "./context/EngagementContext";
import { NAV_ITEMS } from "./lib/navigation";

// Route-level lazy loading (C1)
const OverviewPage = lazy(() =>
  import("./pages/OverviewPage").then((m) => ({ default: m.OverviewPage }))
);
const EngagementsPage = lazy(() =>
  import("./pages/EngagementsPage").then((m) => ({ default: m.EngagementsPage }))
);
const DiscoveryPage = lazy(() =>
  import("./pages/DiscoveryPage").then((m) => ({ default: m.DiscoveryPage }))
);
const DiagnosticsPage = lazy(() =>
  import("./pages/DiagnosticsPage").then((m) => ({ default: m.DiagnosticsPage }))
);
const PrototypesPage = lazy(() =>
  import("./pages/PrototypesPage").then((m) => ({ default: m.PrototypesPage }))
);
const OutcomesPage = lazy(() =>
  import("./pages/OutcomesPage").then((m) => ({ default: m.OutcomesPage }))
);
const StagePlaceholderPage = lazy(() =>
  import("./pages/StagePlaceholderPage").then((m) => ({
    default: m.StagePlaceholderPage,
  }))
);
const DevComponentsPage = lazy(() =>
  import("./pages/DevComponentsPage").then((m) => ({
    default: m.DevComponentsPage,
  }))
);

export interface AppRoutesProps {
  isDev?: boolean;
}

export function PageLoadingState() {
  return (
    <div
      role="status"
      aria-label="Loading page"
      className="flex min-h-[300px] flex-col items-center justify-center space-y-3 rounded-lg border border-border bg-card p-12 text-center"
    >
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-ink" />
      <p className="font-sans text-sm text-muted">Loading page...</p>
    </div>
  );
}

function NotFoundPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <Eyebrow>Navigation</Eyebrow>
        <h1 className="font-display text-[42px] font-normal leading-[1.1] tracking-tight text-ink">
          Page not found
        </h1>
      </header>
      <EmptyState
        title="This route is not available"
        description="Use the sidebar navigation to open Overview, Engagements, Discovery, Diagnostics, Prototypes, or Outcomes."
      />
    </div>
  );
}

export function AppRoutes({ isDev = import.meta.env.DEV }: AppRoutesProps) {
  const placeholderItems = NAV_ITEMS.filter(
    (item) =>
      item.id !== "overview" &&
      item.id !== "engagements" &&
      item.id !== "diagnostics" &&
      item.id !== "discovery" &&
      item.id !== "prototypes" &&
      item.id !== "outcomes"
  );

  return (
    <EngagementProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/engagements" element={<EngagementsPage />} />
          <Route path="/discovery" element={<DiscoveryPage />} />
          <Route path="/diagnostics" element={<DiagnosticsPage />} />
          <Route path="/prototypes" element={<PrototypesPage />} />
          <Route path="/outcomes" element={<OutcomesPage />} />
          {placeholderItems.map((item) => (
            <Route
              key={item.id}
              path={item.path}
              element={<StagePlaceholderPage item={item} />}
            />
          ))}
          {isDev && (
            <Route path="/dev/components" element={<DevComponentsPage />} />
          )}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </EngagementProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
