import { render, screen } from "@testing-library/react";
import { Suspense, lazy } from "react";
import { describe, expect, it } from "vitest";
import { PageLoadingState } from "../App";

describe("Route-level lazy loading (C1)", () => {
  it("test_lazy_fallback_is_a_designed_loading_state", () => {
    const NeverResolves = lazy(() => new Promise(() => {}));

    render(
      <Suspense fallback={<PageLoadingState />}>
        <NeverResolves />
      </Suspense>
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByLabelText("Loading page")).toBeInTheDocument();
    expect(screen.getByText("Loading page...")).toBeInTheDocument();
  });

  it("test_routes_render_after_lazy_load", async () => {
    const FastComponent = lazy(
      () =>
        new Promise<{ default: React.ComponentType }>((resolve) =>
          setTimeout(
            () =>
              resolve({
                default: () => <div data-testid="lazy-loaded">Loaded Content</div>,
              }),
            10
          )
        )
    );

    render(
      <Suspense fallback={<PageLoadingState />}>
        <FastComponent />
      </Suspense>
    );

    expect(screen.getByRole("status")).toBeInTheDocument();
    const resolved = await screen.findByTestId("lazy-loaded");
    expect(resolved).toBeInTheDocument();
    expect(resolved).toHaveTextContent("Loaded Content");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
