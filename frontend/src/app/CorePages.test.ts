import { describe, expect, it } from "vitest";
import { groupWorkItems } from "./CorePages";

describe("work item catalog", () => {
  it("shows one name per phase while retaining every linked location", () => {
    const items = [
      { id: "a", code: "01", name: "Đục bỏ bê tông", component: "Cọc A", status: "planned" },
      { id: "b", code: "02", name: " đục bỏ bê tông ", component: "Cọc B", status: "completed" },
      { id: "c", code: "03", name: "Lắp đặt vỏ cọc", status: "planned" },
    ];
    const groups = groupWorkItems(items);
    expect(groups.get("Đục phá")?.size).toBe(1);
    expect(groups.get("Đục phá")?.get("đục bỏ bê tông")?.map((item) => item.id)).toEqual(["a", "b"]);
    expect(groups.get("Lắp đặt và bơm vữa")?.size).toBe(1);
  });
});
