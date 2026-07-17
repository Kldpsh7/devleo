from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "realistic-sculpt-v1"


def test_realistic_identity_candidate_is_project_owned_and_isolated() -> None:
    identity = json.loads((PROTOTYPE / "identity-qa.json").read_text(encoding="utf-8"))

    assert identity["runtime_replacement"] is False
    assert identity["third_party_mesh"] is False
    assert identity["project_owned_reference"] is True
    assert identity["mechanical_qa"] == "pass"
    assert identity["visual_identity"] == "candidate"


def test_realistic_identity_candidate_keeps_source_and_turntable() -> None:
    seed = ROOT / "assets" / "source-3d" / "leo-realistic-seed.blend"
    source = ROOT / "assets" / "source-3d" / "leo-realistic.blend"
    qa = json.loads((PROTOTYPE / "qa.json").read_text(encoding="utf-8"))
    turntable = QImage(str(PROTOTYPE / "turntable-contact-sheet.png"))

    assert seed.stat().st_size > 1_000_000
    assert source.stat().st_size > 1_000_000
    assert qa["ok"] is True
    assert qa["view_count"] == 8
    assert qa["maximum_corner_alpha"] == 0
    assert qa["edge_failures"] == []
    assert not turntable.isNull()
    assert turntable.hasAlphaChannel() is False
