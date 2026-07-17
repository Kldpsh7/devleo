from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "idle-v1"


def test_blender_idle_prototype_retains_passing_qa_snapshot() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))

    assert qa["ok"] is True
    assert qa["frame_count"] == 12
    assert qa["dimensions"] == [1152, 1248]
    assert qa["mode"] == "RGBA"
    assert qa["maximum_corner_alpha"] == 0
    assert qa["hidden_rgb_pixels_under_zero_alpha"] == 0
    assert qa["touches_safety_edge"] is False


def test_blender_idle_prototype_keeps_source_and_review_artifacts() -> None:
    source = ROOT / "assets" / "source-3d" / "leo.blend"
    neutral = QImage(str(PROTOTYPE / "neutral.png"))

    assert source.stat().st_size > 100_000
    assert not neutral.isNull()
    assert (neutral.width(), neutral.height()) == (1152, 1248)
    assert neutral.hasAlphaChannel()
    for artifact in ("contact-sheet.png", "background-qa.png", "idle-preview.gif", "visual-qa.txt"):
        assert (PROTOTYPE / artifact).stat().st_size > 0
