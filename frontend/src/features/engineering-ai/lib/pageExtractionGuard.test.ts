import { describe, expect, it } from "vitest";
import {
  extractionScopeKey,
  isExtractionInScope,
  isStaleExtractionResponse,
} from "./pageExtractionGuard";

describe("page extraction request guard", () => {
  const row = {
    project_id: "project-1",
    document_id: "document-1",
    page_number: 2,
  };

  it("accepts only the exact project/document/page scope", () => {
    expect(isExtractionInScope(row, "project-1", "document-1", 2)).toBe(true);
    expect(isExtractionInScope(row, "project-2", "document-1", 2)).toBe(false);
    expect(isExtractionInScope(row, "project-1", "document-2", 2)).toBe(false);
    expect(isExtractionInScope(row, "project-1", "document-1", 3)).toBe(false);
  });

  it("builds distinct stable scope keys", () => {
    expect(extractionScopeKey("p1", "d1", 2)).toBe("p1|d1|2");
    expect(extractionScopeKey("p1", "d1", 2)).not.toBe(
      extractionScopeKey("p1", "d1", 3),
    );
  });

  it("rejects a response from an older request", () => {
    expect(isStaleExtractionResponse(3, 3)).toBe(false);
    expect(isStaleExtractionResponse(2, 3)).toBe(true);
    expect(isStaleExtractionResponse(3, 4)).toBe(true);
  });
});
