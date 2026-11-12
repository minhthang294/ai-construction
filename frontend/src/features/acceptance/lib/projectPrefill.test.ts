import { describe, expect, it } from "vitest";
import {
  mergeProjectMetadata,
  projectMetadataDefaults,
} from "./projectPrefill";
import type { ProjectContext } from "../types";

const project: ProjectContext = {
  id: "p1",
  name: "Công trình DAP",
  client: "Công ty DAP - Vinachem",
  location: "Hải Phòng",
  report_title: "Báo cáo ngày",
};

describe("project metadata prefill", () => {
  it("maps project setup fields used by PYC and BBNT", () => {
    expect(projectMetadataDefaults(project)).toEqual({
      project_name: "Công trình DAP",
      client: "Công ty DAP - Vinachem",
      project_location: "Hải Phòng",
      investor_org: "Công ty DAP - Vinachem",
    });
  });

  it("fills only blank values and preserves PYC-specific overrides", () => {
    expect(
      mergeProjectMetadata(
        {
          project_name: "",
          client: undefined,
          project_location: "  ",
          investor_org: "Đơn vị chủ đầu tư riêng",
        },
        project,
      ),
    ).toEqual({
      project_name: "Công trình DAP",
      client: "Công ty DAP - Vinachem",
      project_location: "Hải Phòng",
      investor_org: "Đơn vị chủ đầu tư riêng",
    });
  });

  it("returns blank defaults when project setup is unavailable", () => {
    expect(projectMetadataDefaults(null)).toEqual({
      project_name: "",
      client: "",
      project_location: "",
      investor_org: "",
    });
  });
});
