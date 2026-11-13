import { describe, expect, it } from "vitest";
import {
  buildRequestDefaults,
  latestRequestForPrefill,
  todayIso,
} from "./requestPrefill";
import type { AcceptanceRequest, ProjectContext } from "../types";

const project: ProjectContext = {
  id: "p1",
  name: "Công trình DAP",
  client: "Công ty DAP - Vinachem",
  location: "Hải Phòng",
};

function request(overrides: Partial<AcceptanceRequest> = {}): AcceptanceRequest {
  return {
    id: "req-1",
    project_id: "p1",
    number: "YC-51",
    status: "submitted",
    requested_at: "2026-11-13T08:00:00+07:00",
    revision: 1,
    project_name: "Tên cũ",
    client: "Chủ đầu tư cũ",
    project_location: "Địa điểm cũ",
    location: "8 dầm phân đoạn 1 - cầu chính",
    request_date: "2026-11-12",
    inspection_time: "15h00",
    content: "Đục bê tông om vỡ",
    subject: "Dầm phát sinh",
    field: "construction",
    urgency: "urgent",
    requested_by_profile_id: "profile-contractor",
    supervisor_profile_id: "profile-supervisor",
    investor_profile_id: "profile-investor",
    requested_by_name: "Nguyễn Văn A",
    supervisor_name: "Trần Văn B",
    investor_name: "Lê Văn C",
    contractor_org: "Nhà thầu ABC",
    supervisor_org: "TVGS XYZ",
    investor_org: "Chủ đầu tư 123",
    notes: "Ghi chú cũ",
    created_at: "2026-11-13T08:00:00+07:00",
    updated_at: "2026-11-13T08:00:00+07:00",
    ...overrides,
  };
}

describe("request prefill", () => {
  it("prefers the latest submitted PYC and falls back to a draft", () => {
    const draft = request({
      id: "draft",
      number: "YC-52",
      status: "draft",
      requested_at: "2026-11-13T10:00:00+07:00",
    });
    const olderSubmitted = request({
      id: "submitted-old",
      number: "YC-50",
      requested_at: "2026-11-12T10:00:00+07:00",
    });
    const newerSubmitted = request({
      id: "submitted-new",
      number: "YC-51",
      requested_at: "2026-11-13T09:00:00+07:00",
    });

    expect(
      latestRequestForPrefill([draft, olderSubmitted, newerSubmitted])?.number,
    ).toBe("YC-51");
    expect(latestRequestForPrefill([draft])?.status).toBe("draft");
    expect(latestRequestForPrefill([])).toBeNull();
  });

  it("reuses header/organisation fields but resets request-specific content", () => {
    const defaults = buildRequestDefaults(
      request(),
      project,
      "2026-11-13",
    );

    expect(defaults).toMatchObject({
      project_name: "Công trình DAP",
      client: "Công ty DAP - Vinachem",
      project_location: "Hải Phòng",
      location: "8 dầm phân đoạn 1 - cầu chính",
      request_date: "2026-11-13",
      field: "construction",
      urgency: "urgent",
      requested_by_name: "Nguyễn Văn A",
      supervisor_name: "Trần Văn B",
      investor_name: "Lê Văn C",
      contractor_org: "Nhà thầu ABC",
      supervisor_org: "TVGS XYZ",
      investor_org: "Chủ đầu tư 123",
    });
    expect(defaults).not.toHaveProperty("content");
    expect(defaults).not.toHaveProperty("subject");
    expect(defaults).not.toHaveProperty("number");
    expect(defaults).not.toHaveProperty("notes");
    expect(defaults).not.toHaveProperty("daily_report_id");
  });

  it("falls back to project client when previous investor org is blank", () => {
    const defaults = buildRequestDefaults(
      request({ investor_org: "  " }),
      project,
      "2026-11-13",
    );
    expect(defaults.investor_org).toBe("Công ty DAP - Vinachem");
  });

  it("creates a blank form with today's date when there is no previous PYC", () => {
    const defaults = buildRequestDefaults(null, project, "2026-11-13");
    expect(defaults).toMatchObject({
      project_name: "Công trình DAP",
      client: "Công ty DAP - Vinachem",
      project_location: "Hải Phòng",
      location: "",
      request_date: "2026-11-13",
      urgency: "normal",
      contractor_org: "",
      supervisor_org: "",
      investor_org: "Công ty DAP - Vinachem",
    });
  });

  it("returns an ISO date in Vietnam time", () => {
    expect(todayIso(new Date("2026-11-12T18:30:00Z"))).toBe("2026-11-13");
  });
});
