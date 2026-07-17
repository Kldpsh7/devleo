from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "gaze-directions-v1"
DIRECTIONS = (
    "000",
    "022.5",
    "045",
    "067.5",
    "090",
    "112.5",
    "135",
    "157.5",
    "180",
    "202.5",
    "225",
    "247.5",
    "270",
    "292.5",
    "315",
    "337.5",
)


def load_json(name: str) -> dict[str, object]:
    return json.loads((PROTOTYPE / name).read_text(encoding="utf-8"))


def test_gaze_family_passes_deterministic_render_checks() -> None:
    qa = load_json("qa.json")

    assert qa["ok"] is True
    assert qa["directions"] == list(DIRECTIONS)
    assert qa["dimensions"] == [1152, 1248]
    assert qa["normal_cell_dimensions"] == [192, 208]
    assert qa["hidden_rgb_pixels_under_zero_alpha"] == 0
    assert qa["maximum_center_drift_px"] <= 18
    assert qa["maximum_baseline_drift_px"] == 0
    assert qa["unique_frame_hashes"] == 16
    assert len(qa["continuity"]) == 16


def test_gaze_family_passes_loop_and_blind_direction_gates() -> None:
    continuity = load_json("look-continuity.json")
    blind = load_json("direction-blind-validation.json")

    assert continuity["ok"] is True
    assert continuity["reviewRequired"] is False
    assert continuity["warnings"] == []
    assert continuity["alphaHoles"] == []
    assert len(continuity["pairs"]) == 16

    assert blind["ok"] is True
    assert blind["errors"] == []
    assert blind["unconfirmed"] == []
    hard_pairs = [pair for pair in blind["pairs"] if pair["gate"] == "hard"]
    assert len(hard_pairs) == 2
    assert all(pair[slot]["pass"] is True for pair in hard_pairs for slot in ("A", "B"))
    assert blind["warnings"] == ["horizontal-1 A horizontal axis is ambiguous"]


def test_gaze_family_retains_three_blind_reviews_and_final_semantics() -> None:
    semantics = load_json("direction-semantics.json")

    assert semantics["ok"] is True
    assert semantics["status"] == "approved-for-runtime-integration"
    assert list(semantics["directions"]) == list(DIRECTIONS)
    assert all(semantics["directions"][direction]["verdict"] == "pass" for direction in DIRECTIONS)
    assert len(semantics["review_warnings"]) == 1

    for review_number in range(1, 4):
        verdict = load_json(f"direction-blind-verdicts-{review_number}.json")
        assert len(verdict["pairs"]) == 14
        assert len({pair["pair"] for pair in verdict["pairs"]}) == 14


def test_gaze_family_keeps_visual_qa_artifacts() -> None:
    for name in (
        "gaze-directions.png",
        "gaze-atlas-qa.webp",
        "look-directions.png",
        "direction-blind-pairs.png",
    ):
        assert not QImage(str(PROTOTYPE / name)).isNull()

    preview = QImageReader(str(PROTOTYPE / "gaze-preview.gif"))
    assert preview.canRead()
    assert (PROTOTYPE / "visual-qa.txt").stat().st_size > 0
