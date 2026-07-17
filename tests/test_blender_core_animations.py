from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "core-motion-v1"
EXPECTED = {
    "waiting": (12, 210, True),
    "working": (16, 145, True),
    "review": (12, 210, True),
    "failure": (14, 140, False),
}


def test_core_motion_retains_passing_qa_snapshot() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))

    assert qa["ok"] is True
    assert list(qa["animations"]) == list(EXPECTED)
    for name, (count, duration, loop) in EXPECTED.items():
        animation = qa["animations"][name]
        assert animation["ok"] is True
        assert animation["frame_count"] == count
        assert animation["frame_duration_ms"] == duration
        assert animation["loop"] is loop
        assert animation["dimensions"] == [1152, 1248]
        assert animation["hidden_rgb_pixels_under_zero_alpha"] == 0
        assert animation["touches_safety_edge"] is False
        assert animation["maximum_baseline_drift_px"] <= 4
        assert animation["unique_frame_hashes"] >= count // 2


def test_core_motion_keeps_review_artifacts() -> None:
    for name in EXPECTED:
        sheet = QImage(str(PROTOTYPE / f"{name}-contact-sheet.png"))
        preview = QImageReader(str(PROTOTYPE / f"{name}-preview.gif"))
        assert not sheet.isNull()
        assert preview.canRead()
        # GIF encoders may coalesce visually identical preview frames while preserving
        # their total duration. Exact master counts are asserted from QA above.
        assert preview.imageCount() >= 2
    assert (PROTOTYPE / "visual-qa.txt").stat().st_size > 0
