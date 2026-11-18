import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  Button,
  DataTable,
  EVIDENCE_TYPES,
  StatusPill,
  TypeLabel,
  type DataTableColumn,
  type StatusPillVariant,
} from "../components/ui";

interface TestRow extends Record<string, unknown> {
  label: string;
  count: number;
}

const TEST_COLUMNS: DataTableColumn<TestRow>[] = [
  { key: "label", header: "Category" },
  { key: "count", header: "Tickets", numeric: true },
];

describe("Shared UI components", () => {
  it("StatusPill renders its text label for every variant", () => {
    const variants: Array<{ variant: StatusPillVariant; label: string }> = [
      { variant: "neutral", label: "In progress" },
      { variant: "info", label: "Awaiting approval" },
      { variant: "success", label: "Approved" },
      { variant: "warning", label: "Needs validation" },
      { variant: "danger", label: "Blocked" },
    ];

    render(
      <div>
        {variants.map(({ variant, label }) => (
          <StatusPill key={variant} variant={variant} label={label} />
        ))}
      </div>
    );

    for (const { label } of variants) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("TypeLabel renders all seven types with their text", () => {
    expect(EVIDENCE_TYPES).toHaveLength(7);

    render(
      <div>
        {EVIDENCE_TYPES.map((type) => (
          <TypeLabel key={type} type={type} />
        ))}
      </div>
    );

    for (const type of EVIDENCE_TYPES) {
      expect(screen.getByText(type)).toBeInTheDocument();
    }
  });

  it("Button in loading state is disabled and exposes aria-busy", () => {
    render(<Button loading>Submit proposal</Button>);

    const button = screen.getByRole("button", { name: "Submit proposal" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("DataTable renders empty, loading and error states", () => {
    const { rerender } = render(
      <DataTable
        columns={TEST_COLUMNS}
        data={[]}
        rowKey={(_, idx) => String(idx)}
        emptyTitle="No ticket rows"
        emptyDescription="Upload a dataset to begin."
      />
    );
    expect(screen.getByText("No ticket rows")).toBeInTheDocument();

    rerender(
      <DataTable
        columns={TEST_COLUMNS}
        data={[]}
        rowKey={(_, idx) => String(idx)}
        loading
      />
    );
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Loading table data...")).toBeInTheDocument();

    rerender(
      <DataTable
        columns={TEST_COLUMNS}
        data={[]}
        rowKey={(_, idx) => String(idx)}
        error="Failed to load metrics"
      />
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Failed to load metrics")).toBeInTheDocument();
  });

  it("DataTable right-aligns numeric columns", () => {
    render(
      <DataTable
        columns={TEST_COLUMNS}
        data={[{ label: "Order tracking", count: 412 }]}
        rowKey={(row) => row.label}
      />
    );

    const categoryHeader = screen.getByRole("columnheader", {
      name: "Category",
    });
    const ticketsHeader = screen.getByRole("columnheader", { name: "Tickets" });
    const categoryCell = screen.getByRole("cell", { name: "Order tracking" });
    const ticketsCell = screen.getByRole("cell", { name: "412" });

    expect(categoryHeader.className).toContain("text-left");
    expect(ticketsHeader.className).toContain("text-right");
    expect(categoryCell.className).toContain("text-left");
    expect(ticketsCell.className).toContain("text-right");
    expect(ticketsCell.className).toContain("tabular-nums");
  });
});
