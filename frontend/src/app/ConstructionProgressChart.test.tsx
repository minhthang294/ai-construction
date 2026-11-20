import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ConstructionProgressChart from "./ConstructionProgressChart";

describe("construction progress charts", () => {
  it("shows the percentage and each recorded status against the verified count", () => {
    const html = renderToStaticMarkup(
      <ConstructionProgressChart summary={{
        components: { verified: 8 },
        construction: { completed: 2, in_progress: 3, not_started: 2, blocked: 1, completion_ratio: 0.25 },
      }} />,
    );
    expect(html).toContain("25%");
    expect(html).toContain("2/8 cấu kiện");
    expect(html).toContain("Trạng thái ghi nhận gần nhất");
    expect(html).toContain("Đang thi công");
    expect(html).toContain("37,5%");
    expect(html).toContain("Tạm dừng");
  });

  it("shows an empty message instead of zero progress for a project without verified components", () => {
    const html = renderToStaticMarkup(
      <ConstructionProgressChart summary={{
        components: { verified: 0 },
        construction: { completed: 0, in_progress: 0, not_started: 0, blocked: 0, completion_ratio: 0 },
      }} />,
    );
    expect(html).toContain("Chưa có cấu kiện đã xác minh.");
    expect(html).not.toContain("0%");
  });
});
