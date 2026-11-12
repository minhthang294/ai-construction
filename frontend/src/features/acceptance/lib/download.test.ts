import { describe, expect, it } from "vitest";
import {
  downloadFilenameFromResponse,
  fallbackExportFilename,
  filenameFromContentDisposition,
  isTrustedApiUrl,
} from "./api";
import type { AcceptanceExport } from "../types";

const exported: AcceptanceExport = {
  id: "12345678-aaaa-bbbb-cccc-dddddddddddd",
  project_id: "p1",
  kind: "pyc",
  source_id: "source",
  format: "xlsx",
  sha256: "0".repeat(64),
  generated_at: "2026-11-12T00:00:00Z",
};

describe("authenticated export download filename", () => {
  it("keeps a quoted server filename", () => {
    expect(
      filenameFromContentDisposition(
        'attachment; filename="YC-001.xlsx"',
        "fallback.xlsx",
      ),
    ).toBe("YC-001.xlsx");
  });

  it("decodes RFC 5987 filenames", () => {
    expect(
      filenameFromContentDisposition(
        "attachment; filename*=UTF-8''BBNT-001.xlsx",
        "fallback.xlsx",
      ),
    ).toBe("BBNT-001.xlsx");
  });

  it("falls back when the header is absent", () => {
    expect(filenameFromContentDisposition(null, "fallback.xlsx")).toBe(
      "fallback.xlsx",
    );
  });

  it("builds a stable fallback for PYC and BBNT", () => {
    expect(fallbackExportFilename(exported)).toBe("YC-12345678.xlsx");
    expect(
      fallbackExportFilename({ ...exported, kind: "bbnt", format: "pdf" }),
    ).toBe("BBNT-12345678.pdf");
  });

  it("reads the filename from a download response", () => {
    const response = {
      headers: new Headers({
        "Content-Disposition": 'attachment; filename="BBNT-001.xlsx"',
      }),
    } as Pick<Response, "headers">;
    expect(downloadFilenameFromResponse(response, exported)).toBe(
      "BBNT-001.xlsx",
    );
  });

  it("does not trust a foreign absolute download URL", () => {
    expect(
      isTrustedApiUrl(
        "https://evil.example/steal",
        "https://api.example/api/v1",
        "https://app.example",
      ),
    ).toBe(false);
    expect(
      isTrustedApiUrl(
        "https://api.example/api/v1/projects/p1/acceptance-exports/x/download",
        "https://api.example/api/v1",
        "https://app.example",
      ),
    ).toBe(true);
    expect(
      isTrustedApiUrl("/api/v1/projects/p1/acceptance-exports/x/download", "/api/v1", "https://app.example"),
    ).toBe(true);
    expect(isTrustedApiUrl("//evil.example/steal", "/api/v1", "https://app.example")).toBe(false);
  });
});
