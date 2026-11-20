from pathlib import Path
from runpy import run_path


ordered_stage = run_path(str(Path(__file__).resolve().parents[2] / "scripts" / "order_dap_stages.py"))["ordered_stage"]


def test_pile_jacket_and_lamination_keep_distinct_names_and_order():
    jacket = ordered_stage("pile", "Tấm vỏ composite tiền chế sợi carbon dày 1,5 mm", 14)
    assert jacket[0] == "Lắp tấm vỏ composite tiền chế"
    assert ordered_stage("pile", *jacket) == jacket
    assert jacket[1] < ordered_stage("pile", "Hút nước khỏi vỏ composite", 10)[1]
    assert jacket[1] < ordered_stage("pile", "Vữa không co ngót, không trộn đá", 11)[1]
    layers = [ordered_stage("pile", f"Dán ướt sợi carbon dày 1 mm tấm T{i}", 15)
              for i in range(1, 4)]
    assert layers == sorted(layers, key=lambda step: step[1])
    assert all(step[0].startswith("Dán ướt sợi carbon") for step in layers)


def test_beam_formwork_and_reinforcement_are_in_execution_order():
    names = (
        "Đục bê tông om vỡ đáy, sườn dầm",
        "Thay thế, bổ sung cốt thép (YC-52)",
        "Ván khuôn",
        "Vữa không co ngót tính năng cao",
        "Trám lỗ bằng Sumendur80 hoặc tương đương dày 50 mm",
    )
    positions = [ordered_stage("beam", name, pos)[1]
                 for name, pos in zip(names, [1, 2, 30, 6, 23])]
    assert positions == sorted(positions)
    assert ordered_stage("beam", "Công việc chưa đối chiếu", 1) is None
