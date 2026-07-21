from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "core-states-v1"


def test_core_state_contract_retains_passing_qa_snapshot() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))

    assert qa["ok"] is True
    assert qa["states"] == ["idle", "waiting", "working", "review", "failure"]
    assert qa["laptop_lid_degrees"] == [0.0, 48.0, 96.0, 96.0, 0.0]
    assert qa["dimensions"] == [1152, 1248]
    assert qa["hidden_rgb_pixels_under_zero_alpha"] == 0
    assert len(qa["alpha_bboxes"]) == 5


def test_core_state_contract_keeps_review_artifacts() -> None:
    sheet = QImage(str(PROTOTYPE / "state-poses.png"))

    assert not sheet.isNull()
    assert sheet.width() > sheet.height()
    for state in ("idle", "waiting", "working", "review", "failure"):
        image = QImage(str(PROTOTYPE / "states" / f"{state}.png"))
        assert not image.isNull()
        assert (image.width(), image.height()) == (1152, 1248)
        assert image.hasAlphaChannel()
    assert (PROTOTYPE / "visual-qa.txt").stat().st_size > 0
