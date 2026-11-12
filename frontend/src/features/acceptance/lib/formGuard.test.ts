import { describe, expect, it } from "vitest";
import {
  requiresDiscardConfirmation,
  shouldMarkSaved,
  shouldOfferRevision,
} from "./formGuard";

const base = {
  tab: "requests" as const,
  requestDirty: false,
  recordDirty: false,
  hasEditingRequest: true,
  hasDraft: true,
};

describe("requiresDiscardConfirmation", () => {
  it("warns when leaving a dirty PYC tab", () => {
    expect(
      requiresDiscardConfirmation(
        { ...base, requestDirty: true },
        { type: "switch-tab", tab: "records" },
      ),
    ).toBe(true);
  });

  it("warns when leaving a dirty BBNT tab", () => {
    expect(
      requiresDiscardConfirmation(
        { ...base, tab: "records", recordDirty: true },
        { type: "switch-tab", tab: "requests" },
      ),
    ).toBe(true);
  });

  it("does not warn for clean forms or same tab", () => {
    expect(
      requiresDiscardConfirmation(base, { type: "switch-tab", tab: "records" }),
    ).toBe(false);
    expect(
      requiresDiscardConfirmation(
        { ...base, requestDirty: true },
        { type: "switch-tab", tab: "requests" },
      ),
    ).toBe(false);
  });

  it("warns for close and edit-request only when dirty", () => {
    expect(
      requiresDiscardConfirmation(
        { ...base, requestDirty: true },
        { type: "close-request" },
      ),
    ).toBe(true);
    expect(
      requiresDiscardConfirmation(
        { ...base, requestDirty: true },
        { type: "edit-request" },
      ),
    ).toBe(true);
    expect(
      requiresDiscardConfirmation(base, { type: "close-record" }),
    ).toBe(false);
  });

  it("warns for closing a dirty BBNT draft", () => {
    expect(
      requiresDiscardConfirmation(
        { ...base, tab: "records", recordDirty: true },
        { type: "close-record" },
      ),
    ).toBe(true);
  });
});

describe("shouldOfferRevision", () => {
  it("offers revision only for confirmed or stale records", () => {
    expect(shouldOfferRevision("draft", false)).toBe(false);
    expect(shouldOfferRevision("draft", true)).toBe(true);
    expect(shouldOfferRevision("confirmed", false)).toBe(true);
  });
});

describe("shouldMarkSaved", () => {
  it("keeps dirty when the parent reports a failed save", () => {
    expect(shouldMarkSaved(false)).toBe(false);
    expect(shouldMarkSaved(true)).toBe(true);
    expect(shouldMarkSaved(undefined)).toBe(true);
  });
});
