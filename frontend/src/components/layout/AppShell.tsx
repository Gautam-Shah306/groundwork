import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-canvas text-ink">
      {/* Desktop persistent sidebar */}
      <div className="hidden lg:block lg:shrink-0">
        <div className="sticky top-0 h-screen">
          <Sidebar />
        </div>
      </div>

      {/* Mobile/tablet drawer sidebar */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="relative z-50 h-full">
            <Sidebar onNavigate={() => setMobileNavOpen(false)} />
          </div>
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setMobileNavOpen(false)}
            className="flex-1 bg-ink/20"
          />
        </div>
      )}

      {/* Main flexible workspace */}
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onToggleMobileNav={() => setMobileNavOpen((prev) => !prev)} />
        <main className="mx-auto w-full max-w-[var(--content-max-width)] flex-1 px-5 py-8 lg:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
