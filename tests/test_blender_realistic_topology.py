from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "realistic-topology-v1"


def test_realistic_topology_candidate_is_clean_and_isolated() -> None:
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))
    topology = qa["mechanical_topology"]
    source_mesh = topology["source"]["mesh"]
    result_mesh = topology["result"]["mesh"]

    assert qa["ok"] is True
    assert qa["runtime_replacement"] is False
    assert topology["third_party_mesh"] is False
    assert topology["project_owned_reference"] is True
    assert result_mesh["faces"] < source_mesh["faces"]
    assert result_mesh["face_sides"] == {"4": result_mesh["faces"]}
    assert result_mesh["boundary_edges"] == 0
    assert result_mesh["nonmanifold_edges"] == 0
    assert result_mesh["isolated_vertices"] == 0
    assert result_mesh["mesh_islands"] == 1
    assert 0.98 <= topology["volume_ratio"] <= 1.02
    assert len(topology["result"]["packed_images"]) == 4
    assert all(image["packed"] for image in topology["result"]["packed_images"])


def test_realistic_topology_candidate_preserves_identity_artifacts() -> None:
    source = ROOT / "assets" / "source-3d" / "leo-realistic-topology.blend"
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))
    identity = qa["identity_preservation"]
    turntable = QImage(str(PROTOTYPE / "turntable-contact-sheet.png"))

    assert source.stat().st_size > 1_000_000
    assert identity["minimum_alpha_iou"] >= identity["minimum_alpha_iou_gate"]
    assert identity["maximum_channel_mad"] <= identity["maximum_channel_mad_gate"]
    assert len(identity["views"]) == 8
    assert not turntable.isNull()
    assert turntable.hasAlphaChannel() is False
