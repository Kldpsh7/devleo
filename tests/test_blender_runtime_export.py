from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PySide6.QtGui import QImage, QImageReader

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "assets" / "renders" / "prototypes" / "runtime-export-v1"
PACKAGE = PROTOTYPE / "package" / "leo-the-dev"
QA = PROTOTYPE / "qa"


def test_runtime_export_retains_valid_v2_density_package() -> None:
    pet = json.loads((PACKAGE / "pet.json").read_text(encoding="utf-8"))
    validation = json.loads((PACKAGE / "validation.json").read_text(encoding="utf-8"))
    export_qa = json.loads((QA / "runtime-export.json").read_text(encoding="utf-8"))

    assert pet == {
        "id": "leo-the-dev",
        "displayName": "Leo the Dev",
        "description": "A playful Blender-rendered lion cub coding companion with a silver laptop.",
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.webp",
    }
    assert validation["ok"] is True
    assert validation["sprite_version_number"] == 2
    assert validation["transparent_rgb_residue_pixels"] == 0
    assert validation["errors"] == []
    assert validation["warnings"] == []
    assert export_qa["ok"] is True
    assert all(density["ok"] for density in export_qa["densities"].values())

    expected_sizes = {
        "spritesheet.webp": (1536, 2288),
        "spritesheet@2x.webp": (3072, 4576),
        "spritesheet@4x.webp": (6144, 9152),
    }
    for name, expected_size in expected_sizes.items():
        reader = QImageReader(str(PACKAGE / name))
        size = reader.size()
        assert reader.canRead()
        assert (size.width(), size.height()) == expected_size

    expected_hashes = dict(
        line.split(maxsplit=1)
        for line in (PACKAGE / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    )
    for expected_hash, name in expected_hashes.items():
        assert hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() == expected_hash


def test_runtime_export_retains_direction_and_visual_approval() -> None:
    blind = json.loads((QA / "direction-blind-validation.json").read_text(encoding="utf-8"))
    resolution = json.loads((QA / "blind-review-resolution.json").read_text(encoding="utf-8"))
    semantics = json.loads((QA / "direction-semantics.json").read_text(encoding="utf-8"))
    continuity = json.loads((QA / "look-continuity.json").read_text(encoding="utf-8"))
    despill = json.loads((QA / "chroma-despill-extended.json").read_text(encoding="utf-8"))

    assert blind["ok"] is True
    assert blind["reviewRequired"] is True
    assert len(blind["warnings"]) == 2
    assert resolution["decision"] == "accept"
    assert resolution["severity"] == "minor"
    assert semantics["ok"] is True
    assert semantics["directions"]["157.5"]["verdict"] == "warning"
    assert semantics["directions"]["202.5"]["verdict"] == "warning"
    assert continuity["ok"] is True
    assert continuity["reviewRequired"] is False
    assert despill["ok"] is True
    assert despill["alpha_preserved"] is True
    assert "visual_qa=pass" in (QA / "visual-qa.txt").read_text(encoding="utf-8")

    atlas = QImage(str(PACKAGE / "spritesheet.webp"))
    neutral = atlas.copy(6 * 192, 0, 192, 208)
    unused = atlas.copy(7 * 192, 0, 192, 208)
    assert not neutral.isNull()
    assert any(neutral.pixelColor(x, y).alpha() > 0 for y in range(208) for x in range(192))
    assert all(unused.pixelColor(x, y).alpha() == 0 for y in range(208) for x in range(192))


def test_runtime_export_retains_actual_size_motion_evidence() -> None:
    expected = {
        "failure",
        "gaze",
        "idle",
        "idle-to-walk-left",
        "idle-to-walk-right",
        "jump",
        "review",
        "run-left",
        "run-right",
        "waiting",
        "walk-left",
        "walk-left-to-idle",
        "walk-right",
        "walk-right-to-idle",
        "wave",
        "working",
    }
    previews = {path.stem: path for path in (QA / "previews").glob("*.gif")}
    assert set(previews) == expected
    for path in previews.values():
        reader = QImageReader(str(path))
        assert reader.canRead()
        assert reader.imageCount() >= 6

    assert not QImage(str(QA / "contact-sheet.png")).isNull()
    assert not QImage(str(QA / "look-directions.png")).isNull()
