import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { EmptyState, Eyebrow } from "./components/ui";
import { EngagementProvider } from "./context/EngagementContext";
import { NAV_ITEMS } from "./lib/navigation";
import { DevComponentsPage } from "./pages/DevComponentsPage";
import { DiagnosticsPage } from "./pages/DiagnosticsPage";
import { DiscoveryPage } from "./pages/DiscoveryPage";
import { EngagementsPage } from "./pages/EngagementsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { StagePlaceholderPage } from "./pages/StagePlaceholderPage";

export interface AppRoutesProps {
  isDev?: boolean;
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
      item.id !== "discovery"
  );

  return (
    <EngagementProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/engagements" element={<EngagementsPage />} />
          <Route path="/discovery" element={<DiscoveryPage />} />
          <Route path="/diagnostics" element={<DiagnosticsPage />} />
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
