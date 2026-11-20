import { describe, expect, it } from "vitest";
import {
  bytesToBase64,
  canCommitPreview,
  buildCommitPayload,
  buildManualComponentPayload,
  EMPTY_COMPONENT_FILTERS,
  EMPTY_MANUAL_COMPONENT,
  filterPreviewComponents,
  manualComponentError,
  newIdempotencyKey,
  summarizePreview,
  type ComponentCandidate,
  type ComponentPreview,
  type ManualComponentDraft,
} from "./componentImport";

function candidate(overrides: Partial<ComponentCandidate> = {}): ComponentCandidate {
  return {
    source_id: "C-001",
    source_row: 5,
    zone: "Khu A",
    type: "pile",
    segment: 1,
    design_group: null,
    canonical_code: "I36",
    raw_code: "I36",
    scope: "DESIGN_SCOPE",
    drawing: "KC-01",
    source: "Bản vẽ KC-01",
    verification: "NEEDS_REVIEW",
    aliases: [],
    ...overrides,
  };
}

function preview(overrides: Partial<ComponentPreview> = {}): ComponentPreview {
  return {
    source_sha256: "a".repeat(64),
    components: [candidate()],
    work_links: [
      {
        source_id: "C-001",
        code: "I36",
        dm_row: 12,
        seed_row: 34,
        work: "Đục bỏ bê tông om vỡ",
        raw_location: "Cọc I36",
      },
    ],
    segments: [{ source_id: "S-1", zone: "Khu A", number: 1 }],
    conflicts: [],
    ...overrides,
  };
}

describe("component preview filters", () => {
  const rows = [
    candidate(),
    candidate({
      source_id: "C-002",
      source_row: 6,
      zone: "Khu B",
      type: "beam",
      segment: 2,
      canonical_code: "D1",
      raw_code: "I40-42",
      scope: "ADDITIONAL_SCOPE",
      aliases: ["I40-42"],
    }),
  ];

  it("returns every row unchanged for empty filters", () => {
    const result = filterPreviewComponents(rows, EMPTY_COMPONENT_FILTERS);
    expect(result).toEqual(rows);
  });

  it("filters by zone, type, segment, scope and verification without rewriting values", () => {
    const result = filterPreviewComponents(rows, {
      ...EMPTY_COMPONENT_FILTERS,
      zone: "Khu B",
      type: "beam",
      segment: "2",
      scope: "ADDITIONAL_SCOPE",
      verification: "NEEDS_REVIEW",
    });
    expect(result).toHaveLength(1);
    expect(result[0].canonical_code).toBe("D1");
  });

  it("matches aliases, raw codes, source ids and canonical codes case-insensitively", () => {
    expect(
      filterPreviewComponents(rows, { ...EMPTY_COMPONENT_FILTERS, query: "i40-42" }),
    ).toEqual([rows[1]]);
    expect(
      filterPreviewComponents(rows, { ...EMPTY_COMPONENT_FILTERS, query: " c-001 " }),
    ).toEqual([rows[0]]);
    expect(
      filterPreviewComponents(rows, { ...EMPTY_COMPONENT_FILTERS, query: "d1" }),
    ).toEqual([rows[1]]);
  });

  it("matches raw codes even when they differ from canonical codes", () => {
    const row = candidate({ canonical_code: "X1", raw_code: "Y9" });
    expect(
      filterPreviewComponents([row], { ...EMPTY_COMPONENT_FILTERS, query: "y9" }),
    ).toEqual([row]);
  });
});

describe("component preview commit gate", () => {
  it("blocks commit while conflicts remain", () => {
    expect(canCommitPreview(preview({ conflicts: ["Duplicate segment"] }), true)).toBe(false);
  });

  it("blocks commit without a workbook or a usable preview", () => {
    expect(canCommitPreview(preview(), false)).toBe(false);
    expect(
      canCommitPreview(preview({ components: [], segments: [] }), true),
    ).toBe(false);
  });

  it("allows commit only for a conflict-free preview with a workbook", () => {
    expect(canCommitPreview(preview(), true)).toBe(true);
  });

  it("summarises the exact server preview counts", () => {
    expect(summarizePreview(preview())).toEqual({
      components: 1,
      workLinks: 1,
      segments: 1,
      conflicts: 0,
    });
  });
});

describe("component import commit payload", () => {
  it("sends reviewed=true and the untouched preview", () => {
    const source = preview({
      components: [candidate({ canonical_code: "X1", raw_code: "Y9" })],
    });
    const payload = buildCommitPayload(source, "QUJD", "key-1");
    expect(Object.keys(payload).sort()).toEqual([
      "idempotency_key",
      "preview",
      "reviewed",
      "source_file_base64",
    ]);
    expect(payload.reviewed).toBe(true);
    expect(payload.idempotency_key).toBe("key-1");
    expect(payload.source_file_base64).toBe("QUJD");
    expect(payload.preview).toEqual(source);
    expect(payload.preview).toBe(source);
    expect(payload.preview.components[0].raw_code).toBe("Y9");
  });

  it("keeps every work link in the commit payload, not just the visible page", () => {
    const workLinks = Array.from({ length: 949 }, (_, index) => ({
      source_id: `C-${index + 1}`,
      code: `I${index + 1}`,
      dm_row: index + 1,
      seed_row: index + 5,
      work: "Đục bỏ bê tông om vỡ",
      raw_location: `Cọc I${index + 1}`,
    }));
    const payload = buildCommitPayload(
      preview({ work_links: workLinks }),
      "QUJD",
      "key-949",
    );
    expect(payload.preview.work_links).toHaveLength(949);
    expect(payload.preview.work_links[948].seed_row).toBe(953);
  });

  it("passes through every server preview field, including ones added later", () => {
    const source = preview();
    const link = source.work_links[0] as ComponentPreview["work_links"][number] & {
      future_field: string;
    };
    link.future_field = "keep-me";
    expect(link.seed_row).toBe(34);
    const payload = buildCommitPayload(source, "QUJD", "key-2");
    const sent = payload.preview.work_links[0] as typeof link;
    expect(payload.preview).toBe(source);
    expect(sent.seed_row).toBe(34);
    expect(sent.future_field).toBe("keep-me");
  });

  it("builds a stable key per preview and never exceeds the backend limit", () => {
    const key = newIdempotencyKey("a".repeat(64), "0000");
    expect(key).toContain("a".repeat(12));
    expect(key.length).toBeLessThanOrEqual(120);
    expect(newIdempotencyKey("a".repeat(64), "0000")).toBe(key);
    expect(newIdempotencyKey("b".repeat(64), "1111")).not.toBe(key);
  });
});

describe("workbook base64", () => {
  it("encodes raw bytes, not text, so the server can re-check the hash", () => {
    expect(bytesToBase64(new Uint8Array([0, 1, 255]))).toBe("AAH/");
    expect(bytesToBase64(new TextEncoder().encode("XLSX"))).toBe("WExTWA==");
  });
});

describe("manual component form", () => {
  function draft(overrides: Partial<ManualComponentDraft> = {}): ManualComponentDraft {
    return {
      ...EMPTY_MANUAL_COMPONENT,
      segment_id: "seg-1",
      type: "pile",
      raw_code: "I40-42",
      canonical_code: "I-40-42",
      scope: "DESIGN_SCOPE",
      ...overrides,
    };
  }

  it("sends exactly the shared-core fields with trimmed codes", () => {
    const payload = buildManualComponentPayload(
      draft({ raw_code: "  i40-42  ", canonical_code: " I-40-42 " }),
    );
    expect(payload).toEqual({
      segment_id: "seg-1",
      type: "pile",
      raw_code: "i40-42",
      canonical_code: "I-40-42",
      scope: "DESIGN_SCOPE",
    });
    expect(Object.keys(payload).sort()).toEqual([
      "canonical_code",
      "raw_code",
      "scope",
      "segment_id",
      "type",
    ]);
  });

  it("never uppercases codes or invents source/acceptance fields", () => {
    const payload = buildManualComponentPayload(
      draft({ type: "beam", raw_code: "d1", canonical_code: "d-1" }),
    );
    expect(payload.raw_code).toBe("d1");
    expect(payload.canonical_code).toBe("d-1");
    expect("source" in payload).toBe(false);
    expect("verification" in payload).toBe(false);
  });

  it("requires an existing segment and both codes", () => {
    expect(manualComponentError(draft({ segment_id: "" }))).toBe(
      "Chọn phân đoạn đã có.",
    );
    expect(manualComponentError(draft({ raw_code: "   " }))).toBe(
      "Nhập mã gốc.",
    );
    expect(manualComponentError(draft({ canonical_code: "" }))).toBe(
      "Nhập mã chuẩn.",
    );
    expect(manualComponentError(draft())).toBeNull();
  });

  it("requires an explicit type and scope instead of defaulting", () => {
    expect(manualComponentError(draft({ type: "" }))).toBe(
      "Chọn loại cấu kiện.",
    );
    expect(manualComponentError(draft({ scope: "" }))).toBe("Chọn phạm vi.");
    expect(() =>
      buildManualComponentPayload(draft({ type: "", scope: "" })),
    ).toThrow("Chọn loại và phạm vi trước khi gửi.");
  });

  it("rejects codes longer than the backend limit", () => {
    expect(manualComponentError(draft({ raw_code: "x".repeat(121) }))).toBe(
      "Mã gốc tối đa 120 ký tự.",
    );
    expect(
      manualComponentError(draft({ canonical_code: "x".repeat(121) })),
    ).toBe("Mã chuẩn tối đa 120 ký tự.");
  });
});
