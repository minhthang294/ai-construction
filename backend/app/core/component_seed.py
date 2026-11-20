"""Read the supplied component seed without changing the database or source."""

from hashlib import sha256
from io import BytesIO
import re

from openpyxl import load_workbook


def preview_seed(content: bytes) -> dict:
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        components = []
        for row_number, row in enumerate(workbook["DANH_MUC"].iter_rows(min_row=5, values_only=True), 5):
            if row_number > 5004:
                raise ValueError("Too many component rows")
            if not row or not row[0]:
                continue
            if row[6] not in ("Danh mục gốc", "Phát sinh sửa chữa"):
                raise ValueError(f"Unknown repair scope in seed row {row[0]}")
            components.append({
                "source_id": row[0], "source_row": row_number, "zone": row[1],
                "type": {"Cọc": "pile", "Dầm": "beam"}[row[2]],
                "segment": row[3],
                "design_group": row[4] if row[4] in ("Nhóm 2", "Nhóm 3") and row[2] == "Cọc" else None,
                "canonical_code": row[5],
                "scope": "ADDITIONAL_SCOPE" if row[6] == "Phát sinh sửa chữa" else "DESIGN_SCOPE",
                "drawing": row[7], "source": row[8], "verification": "NEEDS_REVIEW",
            })
        links = []
        for number, row in enumerate(workbook["LIEN_KET_CONG_VIEC"].iter_rows(min_row=5, values_only=True), 5):
            if number > 50004:
                raise ValueError("Too many work rows")
            if row and row[0]:
                links.append({"source_id": row[1], "code": row[3], "dm_row": row[4], "seed_row": number,
                              "work": row[6], "raw_location": row[12]})
        segments = []
        for number, row in enumerate(workbook["18_PHAN_DOAN"].iter_rows(min_row=5, values_only=True), 5):
            if number > 1004:
                raise ValueError("Too many segment rows")
            if row and row[0]:
                segments.append({"source_id": row[0], "zone": row[1], "number": row[2]})
        for component in components:
            component["aliases"] = []
            component["raw_code"] = component["canonical_code"]
            if component["type"] == "beam" and component["canonical_code"] == "I-40-42":
                if any(link["source_id"] == component["source_id"] and
                       re.search(r"(?<![A-Za-z0-9-])I40-42(?![A-Za-z0-9-])", str(link["raw_location"]))
                       for link in links):
                    component["aliases"].append("I40-42")
                    component["raw_code"] = "I40-42"
        return {"source_sha256": sha256(content).hexdigest(), "components": components,
                "work_links": links, "segments": segments}
    finally:
        workbook.close()
