from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "transitions-v1"
EXPECTED = (
    "idle-to-walk-right",
    "walk-right-to-idle",
    "idle-to-walk-left",
    "walk-left-to-idle",
)


def test_transitions_retain_passing_deterministic_qa() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))

    assert qa["ok"] is True
    assert list(qa["animations"]) == list(EXPECTED)
    assert qa["exact_reverse_pairs"] == {"right": True, "left": True}
    assert qa["shared_idle_endpoint"] is True
    for name in EXPECTED:
        animation = qa["animations"][name]
        assert animation["ok"] is True
        assert animation["frame_count"] == 20
        assert animation["frame_duration_ms"] == 70
        assert animation["loop"] is False
        assert animation["dimensions"] == [1152, 1248]
        assert animation["normal_cell_dimensions"] == [192, 208]
        assert animation["hidden_rgb_pixels_under_zero_alpha"] == 0
        assert animation["touches_safety_edge"] is False
        assert animation["unique_frame_hashes"] == 20
        assert animation["maximum_adjacent_center_step_px"] <= 50
        assert animation["maximum_adjacent_baseline_step_px"] == 0
        assert animation["maximum_adjacent_bbox_area_ratio"] <= 1.24


def test_transitions_keep_normal_size_visual_evidence() -> None:
    for name in EXPECTED:
        sheet = QImage(str(PROTOTYPE / f"{name}-contact-sheet.png"))
        preview = QImageReader(str(PROTOTYPE / f"{name}-preview.gif"))
        assert not sheet.isNull()
        assert preview.canRead()
        assert preview.imageCount() == 20

    background = QImage(str(PROTOTYPE / "transition-background-qa.png"))
    assert not background.isNull()
    assert (PROTOTYPE / "visual-qa.txt").stat().st_size > 0
