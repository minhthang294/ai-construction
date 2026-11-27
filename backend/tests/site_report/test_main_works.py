"""Main-work catalogue: pattern mapping, grouping and the read-only endpoint."""

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.component_models import StageDefinition
from app.core.main_works import build_main_works, classify, main_work_label


REAL_NAMES = {
    "pile": {
        "Đục bê tông om vỡ dày trung bình t": "pile-demolish",
        "Đục bê tông om vỡ (phát sinh)": "pile-demolish",
        "Tẩy gỉ cốt thép theo tỷ lệ vùng đục": "pile-derust",
        "Vệ sinh bề mặt cọc sau khi đục": "pile-clean",
        "Mài tạo phẳng và vệ sinh trong phạm vi dán sợi": "pile-clean",
        "Cốt thép bổ sung D ≤ 10": "pile-rebar",
        "Khoan lỗ D30, sâu 220 mm": "pile-rebar",
        "Quét epoxy HM-180C3P hoặc tương đương, 0,6 kg/m²": "pile-epoxy",
        "Rắc cát tạo nhám": "pile-sand",
        "Lắp tấm vỏ composite tiền chế": "pile-shell",
        "Quét keo HM-500 hoặc tương đương tại mối nối vỏ composite, 1,56 lít/m²": "pile-shell",
        "Vữa không co ngót, không trộn đá": "pile-grout",
        "Dán ướt sợi carbon dày 1 mm tấm T1": "pile-carbon",
        "Hệ sơn bảo vệ bê tông và FRP": "pile-paint",
    },
    "beam": {
        "Đục bê tông om vỡ dày TB 70 mm": "beam-demolish",
        "Đục lỗ 100 × 50 × 50 mm để đổ vữa": "beam-demolish",
        "Tẩy gỉ cốt thép (50% diện tích đục bê tông)": "beam-derust",
        "Mài vệ sinh bê tông trong vùng dán sợi": "beam-clean",
        "Cốt thép bổ sung D ≥ 18": "beam-rebar",
        "Khoan lỗ gắn thép D14, sâu 150 mm": "beam-rebar",
        "Quét epoxy HM-180C3P hoặc tương đương, 0,8 kg/m²": "beam-epoxy",
        "Phủ cát tạo nhám": "beam-sand",
        "Ván khuôn": "beam-formwork",
        "Vữa không co ngót tính năng cao": "beam-grout",
        "Quét chất dính bám bê tông cũ và mới trong lỗ đổ vữa": "beam-grout",
        "Dán tấm sợi thủy tinh 0,635 mm lớp 1": "beam-frp",
        "Tấm sợi thủy tinh dày 0,635 mm lớp 2": "beam-frp",
        "Sơn bảo vệ bê tông và FRP, lót epoxy 2 thành phần và phủ chống hoá chất/UV": "beam-paint",
    },
}

HIDDEN_NAMES = {
    "pile": [
        "Hút nước khỏi vỏ composite",
        "Đục hà bám chiều dày trung bình 10 mm",
        "Vệ sinh bằng nước sạch, diện tích bề mặt",
        "Vận chuyển đổ thải",
        "Keo gắn cấy thép",
        "Đường hàn h = 10 mm",
        "Trám vá đầu cọc dày trung bình 50 mm",
        "Thợ lặn phục vụ vệ sinh và lắp đặt vỏ",
    ],
    "beam": [
        "Bao tải",
        "Vận chuyển đổ thải",
        "Keo gắn cấy cốt thép",
        "Đường hàn h = 10 mm",
        "Trám phẳng Sumendur80 trong vùng dán sợi theo diện tích sườn",
    ],
}


@pytest.mark.parametrize(
    ("component_type", "name", "key"),
    [
        (component_type, name, key)
        for component_type, names in REAL_NAMES.items()
        for name, key in names.items()
    ],
)
def test_real_main_names_map_to_expected_work(component_type, name, key):
    assert classify(component_type, name) == (key, None)
    assert main_work_label(component_type, name)


@pytest.mark.parametrize(
    ("component_type", "name"),
    [
        (component_type, name)
        for component_type, names in HIDDEN_NAMES.items()
        for name in names
    ],
)
def test_minor_names_are_hidden_not_listed(component_type, name):
    key, reason = classify(component_type, name)
    assert key is None
    assert reason


class Row:
    def __init__(self, id, component_type, name):
        self.id = id
        self.component_type = component_type
        self.name = name


def test_build_groups_each_definition_once_and_reports_gaps():
    rows = [
        Row("p1", "pile", "Đục bê tông om vỡ dày trung bình t"),
        Row("p2", "pile", "Đục bê tông om vỡ (phát sinh)"),
        Row("p3", "pile", "Rắc cát tạo nhám"),
        Row("p4", "pile", "Hút nước khỏi vỏ composite"),
        Row("p5", "pile", "Chưa phân loại"),
        Row("b1", "beam", "Ván khuôn"),
    ]
    result = build_main_works(rows)
    works = result["works"]
    assert [work["key"] for work in works] == [
        "pile-demolish",
        "pile-sand",
        "beam-formwork",
    ]
    assert works[0]["stage_definition_ids"] == ["p1", "p2"]
    assert [work["order"] for work in works] == [1, 6, 7]
    listed = [id_ for work in works for id_ in work["stage_definition_ids"]]
    assert len(listed) == len(set(listed))
    assert [item["id"] for item in result["hidden"]] == ["p4"]
    assert [item["id"] for item in result["unmapped"]] == ["p5"]


def test_endpoint_returns_project_scoped_catalogue(client, db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    with Session() as db:
        db.add_all([
            StageDefinition(
                id="sd-p1", project_id="p1", component_type="pile",
                code="P1", name="Đục bê tông om vỡ", position=1,
            ),
            StageDefinition(
                id="sd-p2", project_id="p1", component_type="pile",
                code="P2", name="Dàn giáo", position=2,
            ),
            StageDefinition(
                id="sd-b1", project_id="p1", component_type="beam",
                code="B1", name="Ván khuôn", position=1,
            ),
            StageDefinition(
                id="sd-other", project_id="other", component_type="beam",
                code="X1", name="Ván khuôn", position=1,
            ),
        ])
        db.commit()

    body = client.get("/api/v1/projects/p1/main-works").json()
    assert "works" in body, body
    assert [work["key"] for work in body["works"]] == [
        "pile-demolish",
        "beam-formwork",
    ]
    assert [item["name"] for item in body["unmapped"]] == ["Dàn giáo"]

    pile_only = client.get("/api/v1/projects/p1/main-works?type=pile").json()
    assert [work["component_type"] for work in pile_only["works"]] == ["pile"]
