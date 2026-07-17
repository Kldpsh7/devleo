from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "realistic-rig-v1"


def test_realistic_rig_candidate_has_bounded_complete_weights() -> None:
    mechanical = json.loads((PROTOTYPE / "mechanical-qa.json").read_text(encoding="utf-8"))
    weights = mechanical["weights"]
    topology = mechanical["topology"]

    assert mechanical["ok"] is True
    assert mechanical["runtime_replacement"] is False
    assert mechanical["rig"]["bone_count"] == 22
    assert weights["deform_bone_count"] == 21
    assert weights["unweighted_vertices"] == 0
    assert weights["empty_deform_groups"] == []
    assert weights["maximum_influences_per_vertex"] <= 4
    assert weights["vertices_over_four_influences"] == 0
    assert weights["armature_modifier_count"] == 1
    assert topology["face_sides"] == {"4": topology["faces"]}
    assert topology["boundary_edges"] == 0
    assert topology["nonmanifold_edges"] == 0


def test_realistic_rig_candidate_keeps_deformation_review_artifacts() -> None:
    source = ROOT / "assets" / "source-3d" / "leo-realistic-rig.blend"
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))
    contact = QImage(str(PROTOTYPE / "deformation-contact-sheet.png"))

    assert source.stat().st_size > 1_000_000
    assert qa["ok"] is True
    assert qa["runtime_replacement"] is False
    assert qa["frame_count"] == 12
    assert qa["pose_count"] == 6
    assert qa["views"] == ["side", "front"]
    assert qa["maximum_corner_alpha"] == 0
    assert qa["edge_failures"] == []
    assert all(0.78 <= ratio <= 1.22 for ratio in qa["alpha_area_ratios"])
    assert not contact.isNull()
    assert contact.hasAlphaChannel() is False
