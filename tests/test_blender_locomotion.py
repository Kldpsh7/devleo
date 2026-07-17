from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "locomotion-v1"
EXPECTED = {
    "walk-right": (12, 125, False),
    "walk-left": (12, 125, False),
    "run-right": (12, 85, True),
    "run-left": (12, 85, True),
}


def test_locomotion_retains_passing_deterministic_qa() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))

    assert qa["ok"] is True
    assert list(qa["animations"]) == list(EXPECTED)
    for name, (frame_count, duration, is_run) in EXPECTED.items():
        animation = qa["animations"][name]
        assert animation["ok"] is True
        assert animation["frame_count"] == frame_count
        assert animation["frame_duration_ms"] == duration
        assert animation["loop"] is True
        assert animation["dimensions"] == [1152, 1248]
        assert animation["normal_cell_dimensions"] == [192, 208]
        assert animation["hidden_rgb_pixels_under_zero_alpha"] == 0
        assert animation["touches_safety_edge"] is False
        assert animation["unique_frame_hashes"] == frame_count
        if is_run:
            assert animation["maximum_center_drift_px"] <= 125
            assert animation["maximum_baseline_drift_px"] <= 125
            assert animation["airborne_frames"] >= 3
        else:
            assert animation["maximum_center_drift_px"] <= 24
            assert animation["maximum_baseline_drift_px"] <= 12
            assert animation["airborne_frames"] == 0


def test_locomotion_keeps_normal_size_visual_evidence() -> None:
    for name in EXPECTED:
        sheet = QImage(str(PROTOTYPE / f"{name}-contact-sheet.png"))
        preview = QImageReader(str(PROTOTYPE / f"{name}-preview.gif"))
        assert not sheet.isNull()
        assert preview.canRead()
        assert preview.imageCount() == 12

    background = QImage(str(PROTOTYPE / "locomotion-background-qa.png"))
    assert not background.isNull()
    assert (PROTOTYPE / "visual-qa.txt").stat().st_size > 0
