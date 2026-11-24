import { afterEach, describe, expect, it, vi } from "vitest";
import { AcceptanceApiError } from "../lib/api";
import {
  dailyReportHref,
  dailyReportLabel,
  deleteRequestWarning,
  draftFor,
  draftPayload,
  draftStatusSummary,
  draftTitle,
  errorMessage,
  hasPendingFilter,
  newDraft,
  pendingFilters,
  recordActionLabel,
  recordPickerActionLabel,
  recordPickerLabel,
  requestSubtitle,
  shortDate,
  today,
} from "./acceptancePageModel";
import type { RecordDraft } from "./acceptancePageModel";
import type {
  AcceptanceRecord,
  AcceptanceRequest,
  LinkedDailyReport,
  ProjectContext,
} from "../types";

const project: ProjectContext = {
  id: "p1",
  name: "Công trình DAP",
  client: "Công ty DAP",
  location: "Hải Phòng",
};

function request(overrides: Partial<AcceptanceRequest> = {}): AcceptanceRequest {
  return {
    id: "req-1",
    project_id: "p1",
    number: "YC-51",
    status: "draft",
    requested_at: "2026-11-13T08:00:00+07:00",
    revision: 1,
    project_name: "Tên PYC",
    client: "Chủ đầu tư PYC",
    project_location: "Địa điểm PYC",
    location: "8 dầm phân đoạn 1",
    created_at: "2026-11-13T08:00:00+07:00",
    updated_at: "2026-11-13T08:00:00+07:00",
    ...overrides,
  };
}

function record(overrides: Partial<AcceptanceRecord> = {}): AcceptanceRecord {
  return {
    id: "rec-1",
    project_id: "p1",
    request_id: "req-1",
    number: "BB-01",
    status: "draft",
    revision: 2,
    stale: false,
    reused: {},
    record_date: "2026-11-13",
    start_time: "15h00",
    end_time: null,
    design_compliance: "yes",
    technical_compliance: null,
    other_notes: null,
    conclusion_note: null,
    participants: [
      {
        id: "part-1",
        role: "supervisor",
        person_name: "Trần Văn B",
        organization: null,
        position: "TVGS",
        sort_order: 0,
      },
    ],
    checklist: [
      {
        id: "check-1",
        item: "Hồ sơ thiết kế",
        state: "yes",
        evidence_refs: ["file.pdf"],
        note: null,
        sort_order: 0,
      },
    ],
    created_at: "2026-11-13T08:00:00+07:00",
    updated_at: "2026-11-13T08:00:00+07:00",
    ...overrides,
  };
}

function draft(overrides: Partial<RecordDraft> = {}): RecordDraft {
  return {
    id: "rec-1",
    request_id: "req-1",
    request_number: "YC-51",
    project_name: "Công trình DAP",
    client: "Công ty DAP",
    project_location: "Hải Phòng",
    location: "8 dầm",
    number: "BB-01",
    revision: 1,
    stale: false,
    stale_warning: null,
    status: "draft",
    record_date: "2026-11-13",
    start_time: "15h00",
    end_time: "",
    design_compliance: "",
    technical_compliance: "",
    other_notes: "",
    conclusion_note: "",
    result: null,
    participants: [],
    checklist: [],
    ...overrides,
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("acceptance page date helpers", () => {
  it("formats ISO dates as dd/mm/yyyy and keeps unexpected input", () => {
    expect(shortDate("2026-11-13")).toBe("13/11/2026");
    expect(shortDate("2026-11")).toBe("2026-11");
    expect(shortDate("not-a-date")).toBe("date/a/not");
  });

  it("uses the Vietnam calendar day", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-12T18:30:00Z"));
    expect(today()).toBe("2026-11-13");
  });
});

describe("record draft defaults", () => {
  it("copies a saved record and falls back to project metadata", () => {
    const result = draftFor(record(), undefined, project);
    expect(result).toMatchObject({
      id: "rec-1",
      request_id: "req-1",
      request_number: undefined,
      project_name: "Công trình DAP",
      client: "Công ty DAP",
      project_location: "Hải Phòng",
      location: "",
      number: "BB-01",
      revision: 2,
      status: "draft",
      record_date: "2026-11-13",
      start_time: "15h00",
      end_time: "",
      design_compliance: "yes",
      technical_compliance: "",
      other_notes: "",
      conclusion_note: "",
    });
    expect(result.participants).toEqual([
      {
        role: "supervisor",
        person_name: "Trần Văn B",
        organization: "",
        position: "TVGS",
        sort_order: 0,
      },
    ]);
    expect(result.checklist).toEqual([
      {
        item: "Hồ sơ thiết kế",
        state: "yes",
        evidence_refs: ["file.pdf"],
        note: undefined,
        sort_order: 0,
      },
    ]);
  });

  it("prefers PYC metadata over project defaults", () => {
    const result = draftFor(record(), request(), project);
    expect(result).toMatchObject({
      request_number: "YC-51",
      project_name: "Tên PYC",
      client: "Chủ đầu tư PYC",
      project_location: "Địa điểm PYC",
      location: "8 dầm phân đoạn 1",
    });
  });

  it("creates a blank draft with no reused personnel", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-12T18:30:00Z"));
    const result = newDraft(request({ project_name: null, client: null, project_location: null }), project);
    expect(result).toMatchObject({
      request_id: "req-1",
      request_number: "YC-51",
      project_name: "Công trình DAP",
      client: "Công ty DAP",
      project_location: "Hải Phòng",
      location: "8 dầm phân đoạn 1",
      number: null,
      revision: 1,
      stale: false,
      stale_warning: null,
      status: "draft",
      record_date: "2026-11-13",
      design_compliance: "",
      technical_compliance: "",
      result: null,
      participants: [],
    });
    expect(result.checklist.length).toBeGreaterThan(0);
  });
});

describe("record draft payload", () => {
  it("trims participants, drops blanks and reindexes sort order", () => {
    const payload = draftPayload(
      draft({
        participants: [
          { role: "investor", person_name: "  Lê Văn C  ", sort_order: 9 },
          { role: "contractor", person_name: "   ", sort_order: 5 },
          { role: "supervisor", person_name: "Trần Văn B", sort_order: 7 },
        ],
      }),
    );
    expect(payload.participants).toEqual([
      { role: "investor", person_name: "Lê Văn C", sort_order: 0 },
      { role: "supervisor", person_name: "Trần Văn B", sort_order: 1 },
    ]);
  });

  it("normalises blank optional fields to null", () => {
    const payload = draftPayload(
      draft({
        number: undefined,
        record_date: "",
        start_time: "  ",
        end_time: "",
        design_compliance: "",
        technical_compliance: "",
        other_notes: "  ghi chú  ",
        conclusion_note: "   ",
      }),
    );
    expect(payload).toMatchObject({
      number: null,
      record_date: null,
      start_time: null,
      end_time: null,
      design_compliance: null,
      technical_compliance: null,
      other_notes: "ghi chú",
      conclusion_note: null,
    });
  });

  it("omits participants on first save when the list is empty", () => {
    const payload = draftPayload(
      draft({ id: undefined, participants: [] }),
    );
    expect(payload).not.toHaveProperty("participants");
  });

  it("includes an empty participant list when updating a saved record", () => {
    const payload = draftPayload(draft({ participants: [] }));
    expect(payload.participants).toEqual([]);
  });
});

describe("acceptance page labels", () => {
  it("resolves request subtitles with fallbacks", () => {
    expect(requestSubtitle(request())).toBe("8 dầm phân đoạn 1");
    expect(requestSubtitle(request({ location: null, subject: "Dầm" }))).toBe("Dầm");
    expect(requestSubtitle(request({ location: null, subject: null }))).toBe("Tên PYC");
    expect(
      requestSubtitle(
        request({ location: null, subject: null, project_name: null }),
      ),
    ).toBe("Chưa có nội dung");
  });

  it("formats linked daily reports", () => {
    const report: LinkedDailyReport = {
      id: "r1",
      project_id: "p1",
      report_date: "2026-11-13",
      status: "submitted",
    };
    expect(dailyReportLabel(report)).toBe("2026-11-13 (submitted)");
    expect(dailyReportLabel(null)).toBe("đã liên kết");
    expect(dailyReportHref("p1", "2026-11-13")).toBe(
      "/api/v1/projects/p1/daily-reports/2026-11-13",
    );
  });

  it("labels record actions in the request list", () => {
    expect(recordActionLabel(undefined)).toBe("Tạo BBNT");
    expect(recordActionLabel(record())).toBe("Mở BBNT");
  });

  it("labels the record picker rows", () => {
    expect(recordPickerLabel(request(), undefined)).toBe(
      "PYC YC-51 — chưa có BBNT",
    );
    expect(recordPickerLabel(request(), record({ status: "confirmed" }))).toBe(
      "PYC YC-51 — BBNT Đã xác nhận",
    );
    expect(recordPickerActionLabel(undefined)).toBe("Lập BBNT");
    expect(recordPickerActionLabel(record())).toBe("Mở");
  });

  it("builds the draft heading from number, request or blank state", () => {
    expect(draftTitle(draft())).toBe("BBNT số BB-01 — Bản sửa 1");
    expect(draftTitle(draft({ number: null }))).toBe(
      "BBNT cho PYC YC-51 — Bản sửa 1",
    );
    expect(draftTitle(draft({ number: null, request_number: undefined }))).toBe(
      "BBNT (nháp) — Bản sửa 1",
    );
  });

  it("summarises confirmed and draft status", () => {
    expect(draftStatusSummary(draft({ status: "confirmed", result: "approved" }))).toBe(
      "Đã xác nhận: Đồng ý",
    );
    expect(draftStatusSummary(draft({ status: "confirmed", result: null }))).toBe(
      "Đã xác nhận: —",
    );
    expect(draftStatusSummary(draft())).toBe("Nháp — chưa có kết luận");
  });

  it("warns before deleting a request with a linked record", () => {
    expect(deleteRequestWarning(request(), record())).toBe(
      "PYC YC-51 đã có BBNT (Nháp). Xoá PYC sẽ xoá luôn BBNT liên quan và lịch sử xuất file. Không thể hoàn tác. Tiếp tục?",
    );
    expect(deleteRequestWarning(request({ status: "submitted" }), undefined)).toBe(
      "PYC YC-51 đã gửi. Xoá phiếu này và lịch sử xuất file? Không thể hoàn tác.",
    );
    expect(deleteRequestWarning(request(), undefined)).toBe(
      "Xoá PYC YC-51? Không thể hoàn tác.",
    );
  });

  it("maps API errors and unknown failures to text", () => {
    expect(errorMessage(new AcceptanceApiError(422, "Dữ liệu sai", "INVALID"))).toBe(
      "Dữ liệu sai (INVALID)",
    );
    expect(errorMessage(new AcceptanceApiError(500, "Lỗi máy chủ"))).toBe(
      "Lỗi máy chủ",
    );
    expect(errorMessage(new Error("Mất kết nối"))).toBe("Mất kết nối");
    expect(errorMessage("oops")).toBe("Thao tác thất bại.");
  });
});

describe("pending acceptance filter helpers", () => {
  it("detects a navigation filter", () => {
    expect(hasPendingFilter({})).toBe(false);
    expect(hasPendingFilter(null)).toBe(false);
    expect(hasPendingFilter({ batch_id: "b1" })).toBe(true);
    expect(hasPendingFilter({ stage_definition_id: "s1" })).toBe(true);
  });

  it("builds filter params only when requested", () => {
    expect(pendingFilters({ batch_id: "b1", stage_definition_id: "s1" }, false)).toEqual({});
    expect(pendingFilters({ batch_id: "b1", stage_definition_id: "s1" }, true)).toEqual({
      batch_id: "b1",
      stage_definition_id: "s1",
    });
    expect(pendingFilters(undefined, true)).toEqual({
      batch_id: undefined,
      stage_definition_id: undefined,
    });
  });
});
