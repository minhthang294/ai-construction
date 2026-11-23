import { describe, expect, it } from "vitest";
import { citationDisplay } from "./citations";
import type { Citation } from "../types";

function citation(overrides: Partial<Citation>): Citation {
  return {
    document_id: "doc",
    document_name: "BV-01.pdf",
    version: 1,
    page_number: 2,
    quote: "quote",
    url: "/api/v1/pages/2",
    ...overrides,
  };
}

describe("citationDisplay", () => {
  it("shows page metadata for drawing citations", () => {
    const display = citationDisplay(citation({ drawing_number: "TK-01" }));
    expect(display.isDatabase).toBe(false);
    expect(display.pageLabel).toBe("trang 2");
    expect(display.title).toBe("BV-01.pdf");
  });

  it("extracts component code and record id from a database row", () => {
    const display = citationDisplay(
      citation({
        source: "database",
        document_id: "component-1",
        document_name: "Database · structural_components",
        page_number: 0,
        record_id: "component-1",
        quote: JSON.stringify({ canonical_code: "F67", type: "pile" }),
      }),
    );
    expect(display.isDatabase).toBe(true);
    expect(display.table).toBe("structural_components");
    expect(display.code).toBe("F67");
    expect(display.title).toBe("Cấu kiện F67");
    expect(display.recordId).toBe("component-1");
  });

  it("falls back to table and record id for non-component database rows", () => {
    const display = citationDisplay(
      citation({
        source: "database",
        document_id: "event-1",
        document_name: "Database · component_progress_events",
        page_number: 0,
        record_id: "event-1",
        quote: JSON.stringify({ status: "COMPLETED" }),
      }),
    );
    expect(display.code).toBeNull();
    expect(display.title).toBe("component_progress_events");
    expect(display.recordId).toBe("event-1");
  });
});
