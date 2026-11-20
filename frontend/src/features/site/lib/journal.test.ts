import { describe, expect, it } from "vitest";
import {
  canCreateJournalSnapshot,
  journalBlockerLabel,
  type JournalPreview,
} from "./journal";

function preview(overrides: Partial<JournalPreview> = {}): JournalPreview {
  return {
    project_id: "p1",
    project_title: "Công trình",
    date: "2026-11-18",
    date_display: "18/11/2026",
    reviewed_only: true,
    snapshot_eligible: true,
    blockers: [],
    daily_report: null,
    construction_events: [],
    acceptance_events: [],
    acceptance_count: 0,
    journal: {},
    blank_sections: [],
    warnings: [],
    evidence: [],
    omitted_evidence_refs: [],
    evidence_summary: { evidence_count: 0, omitted_evidence_count: 0 },
    preview_sha256: "a".repeat(64),
    preview_text: "Nội dung",
    ...overrides,
  };
}

describe("journal snapshot gate", () => {
  it("requires an eligible preview, a hash and explicit confirmation", () => {
    expect(canCreateJournalSnapshot(preview(), true)).toBe(true);
    expect(canCreateJournalSnapshot(preview(), false)).toBe(false);
    expect(
      canCreateJournalSnapshot(preview({ snapshot_eligible: false }), true),
    ).toBe(false);
    expect(
      canCreateJournalSnapshot(preview({ preview_sha256: "short" }), true),
    ).toBe(false);
    expect(canCreateJournalSnapshot(null, true)).toBe(false);
  });

  it("labels known blockers without inventing a reason", () => {
    expect(journalBlockerLabel("DAILY_REPORT_NOT_REVIEWED")).toMatch(/chưa được duyệt/);
    expect(journalBlockerLabel("OTHER")).toBe("OTHER");
  });
});
