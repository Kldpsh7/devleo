from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "gestures-v1"
EXPECTED = {
    "wave": (10, 150, 0),
    "jump": (12, 110, 8),
}


def test_gestures_retain_passing_deterministic_qa() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))

    assert qa["ok"] is True
    assert list(qa["animations"]) == list(EXPECTED)
    for name, (frame_count, duration, airborne_frames) in EXPECTED.items():
        animation = qa["animations"][name]
        assert animation["ok"] is True
        assert animation["frame_count"] == frame_count
        assert animation["frame_duration_ms"] == duration
        assert animation["loop"] is False
        assert animation["dimensions"] == [1152, 1248]
        assert animation["normal_cell_dimensions"] == [192, 208]
        assert animation["hidden_rgb_pixels_under_zero_alpha"] == 0
        assert animation["touches_safety_edge"] is False
        assert animation["endpoint_sha256_match"] is True
        assert animation["unique_frame_hashes"] >= frame_count - 2
        assert animation["airborne_frames"] == airborne_frames

    assert qa["animations"]["wave"]["maximum_baseline_drift_px"] == 0
    assert qa["animations"]["jump"]["maximum_center_drift_px"] <= 145
    assert qa["animations"]["jump"]["maximum_baseline_drift_px"] <= 145


def test_gestures_keep_normal_size_visual_evidence() -> None:
    for name, (frame_count, _duration, _airborne) in EXPECTED.items():
        sheet = QImage(str(PROTOTYPE / f"{name}-contact-sheet.png"))
        preview = QImageReader(str(PROTOTYPE / f"{name}-preview.gif"))
        assert not sheet.isNull()
        assert preview.canRead()
        assert preview.imageCount() >= frame_count - 1

    background = QImage(str(PROTOTYPE / "gesture-background-qa.png"))
    assert not background.isNull()
    assert (PROTOTYPE / "visual-qa.txt").stat().st_size > 0
