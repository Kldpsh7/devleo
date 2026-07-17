from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
SUPERSEDED = ROOT / "assets" / "renders" / "prototypes" / "gaze-cardinals-v1"
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "gaze-cardinals-v2"
CARDINALS = ("000", "090", "180", "270")


def test_first_cardinal_candidate_remains_marked_as_superseded() -> None:
    semantics = json.loads((SUPERSEDED / "direction-semantics.json").read_text(encoding="utf-8"))

    assert semantics["ok"] is False
    assert semantics["labeled_review_ok"] is True
    assert semantics["blind_followup_ok"] is False


def test_gaze_cardinals_retain_passing_qa_snapshot() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))
    semantics = json.loads((PROTOTYPE / "direction-semantics.json").read_text(encoding="utf-8"))

    assert qa["ok"] is True
    assert qa["directions"] == list(CARDINALS)
    assert qa["expected"] == ["up", "right", "down", "left"]
    assert qa["dimensions"] == [1152, 1248]
    assert qa["normal_cell_dimensions"] == [192, 208]
    assert qa["hidden_rgb_pixels_under_zero_alpha"] == 0
    assert qa["maximum_baseline_drift_px"] == 0
    assert qa["unique_frame_hashes"] == 4
    assert semantics["ok"] is True
    assert all(semantics["directions"][label]["verdict"] == "pass" for label in CARDINALS)


def test_gaze_cardinals_keep_review_artifacts() -> None:
    sheet = QImage(str(PROTOTYPE / "gaze-directions.png"))
    preview = QImageReader(str(PROTOTYPE / "gaze-preview.gif"))

    assert not sheet.isNull()
    assert preview.canRead()
    for index, label in enumerate(CARDINALS):
        image = QImage(str(PROTOTYPE / "directions" / f"{index:02d}-{label}.png"))
        assert not image.isNull()
        assert (image.width(), image.height()) == (1152, 1248)
        assert image.hasAlphaChannel()
    assert (PROTOTYPE / "visual-qa.txt").stat().st_size > 0
