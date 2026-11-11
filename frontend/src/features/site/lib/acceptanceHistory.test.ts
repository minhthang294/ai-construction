import { describe, expect, it } from "vitest";
import {
  buildFallbackHistory,
  normalizeAcceptanceHistory,
} from "./acceptanceHistory";

describe("acceptance history normalization", () => {
  it("normalizes request/record shapes and keeps stale/warnings", () => {
    const rows = normalizeAcceptanceHistory(
      {
        requests: [
          {
            id: "r1",
            number: "PYC-01",
            status: "submitted",
            work_item_id: "w1",
            revision: 2,
            stale: true,
            warnings: ["PYC đã thay đổi"],
            records: [
              {
                id: "b1",
                number: "BBNT-01",
                status: "confirmed",
                result: "approved",
                revision: 1,
              },
            ],
          },
          {
            id: "r2",
            number: "PYC-02",
            status: "draft",
            work_item_id: "w2",
          },
        ],
      },
      "w1",
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].number).toBe("PYC-01");
    expect(rows[0].stale).toBe(true);
    expect(rows[0].warnings).toEqual(["PYC đã thay đổi"]);
    expect(rows[0].records[0].number).toBe("BBNT-01");
    expect(rows[0].records[0].result).toBe("approved");
  });

  it("accepts a bare array and returns empty on unknown payloads", () => {
    expect(
      normalizeAcceptanceHistory(
        [{ id: "r1", number: "PYC-01", status: "draft" }],
        "w1",
      ),
    ).toHaveLength(1);
    expect(normalizeAcceptanceHistory(null, "w1")).toEqual([]);
    expect(normalizeAcceptanceHistory({ unexpected: true }, "w1")).toEqual([]);
  });

  it("groups the flat work-item history shape by request", () => {
    const rows = normalizeAcceptanceHistory(
      {
        work_item_id: "w1",
        items: [
          {
            kind: "pyc",
            id: "r1",
            number: "PYC-01",
            status: "submitted",
            revision: 2,
          },
          {
            kind: "bbnt",
            id: "b1",
            request_id: "r1",
            number: "BBNT-01",
            status: "draft",
            revision: 1,
            result: null,
          },
        ],
      },
      "w1",
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].number).toBe("PYC-01");
    expect(rows[0].records[0].number).toBe("BBNT-01");
  });
});

describe("acceptance history fallback", () => {
  it("filters by work item and attaches records by request_id", () => {
    const rows = buildFallbackHistory(
      [
        { id: "r1", number: "PYC-01", status: "submitted", work_item_id: "w1" },
        { id: "r2", number: "PYC-02", status: "draft", work_item_id: "w2" },
      ],
      [
        {
          id: "b1",
          request_id: "r1",
          number: "BBNT-01",
          status: "draft",
          result: null,
        },
      ],
      "w1",
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("r1");
    expect(rows[0].records).toHaveLength(1);
    expect(rows[0].records[0].id).toBe("b1");
  });

  it("does not invent requests when the fallback lists are empty", () => {
    expect(buildFallbackHistory([], [], "w1")).toEqual([]);
  });
});
