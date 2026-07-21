"""Render the first canonical Leo state-pose contract from the source scene."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import bpy

STATE_POSES: tuple[dict[str, Any], ...] = (
    {
        "name": "idle",
        "lid_degrees": 0.0,
        "head_rotation": (0.0, 0.0, 0.0),
        "head_offset": (0.0, 0.0, 0.0),
        "tail_rotation": (0.0, 0.0, -2.0),
        "ear_left": (0.0, 0.0, 0.0),
        "ear_right": (0.0, 0.0, 0.0),
        "blink_scale": 1.0,
        "ear_scale_z": 1.0,
    },
    {
        "name": "waiting",
        "lid_degrees": 48.0,
        "head_rotation": (-2.0, 1.0, 7.0),
        "head_offset": (0.0, 0.0, 0.02),
        "tail_rotation": (2.0, 0.0, 4.0),
        "ear_left": (-3.0, 0.0, -4.0),
        "ear_right": (1.0, 0.0, 2.0),
        "blink_scale": 1.0,
        "ear_scale_z": 1.0,
    },
    {
        "name": "working",
        "lid_degrees": 96.0,
        "head_rotation": (11.0, 0.0, 0.0),
        "head_offset": (0.0, -0.02, -0.05),
        "tail_rotation": (-2.0, 0.0, 7.0),
        "ear_left": (1.5, 0.0, -1.0),
        "ear_right": (1.5, 0.0, 1.0),
        "blink_scale": 1.0,
        "ear_scale_z": 1.0,
    },
    {
        "name": "review",
        "lid_degrees": 96.0,
        "head_rotation": (9.0, -1.5, -4.0),
        "head_offset": (-0.02, -0.01, -0.04),
        "tail_rotation": (1.0, 0.0, 1.0),
        "ear_left": (-2.5, 0.0, -3.0),
        "ear_right": (2.0, 0.0, 4.0),
        "blink_scale": 0.55,
        "ear_scale_z": 0.92,
    },
    {
        "name": "failure",
        "lid_degrees": 0.0,
        "head_rotation": (34.0, 0.0, 0.0),
        "head_offset": (0.0, -0.40, -2.62),
        "tail_rotation": (-5.0, 0.0, -9.0),
        "ear_left": (45.0, 0.0, 4.0),
        "ear_right": (45.0, 0.0, -4.0),
        "blink_scale": 0.08,
        "ear_scale_z": 0.52,
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def radians(values: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(math.radians(value) for value in values)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    states_dir = output_dir / "states"
    states_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    controls = {
        name: bpy.data.objects[name]
        for name in (
            "CTRL_Body_Breath",
            "CTRL_Head_Glance",
            "CTRL_Tail_Flick",
            "CTRL_Ear_L",
            "CTRL_Ear_R",
            "CTRL_Blink_L",
            "CTRL_Blink_R",
            "CTRL_Laptop_Lid",
        )
    }
    baselines = {
        name: {
            "location": object_.location.copy(),
            "rotation": object_.rotation_euler.copy(),
            "scale": object_.scale.copy(),
        }
        for name, object_ in controls.items()
    }
    eye_parts = {
        name: bpy.data.objects[name]
        for name in (
            "Eye_L",
            "Eye_R",
            "Iris_L",
            "Iris_R",
            "Pupil_L",
            "Pupil_R",
            "Eye_Glint_L",
            "Eye_Glint_R",
        )
    }
    eye_scale_baselines = {name: object_.scale.copy() for name, object_ in eye_parts.items()}

    entries: list[dict[str, object]] = []
    for pose in STATE_POSES:
        for name, object_ in controls.items():
            object_.location = baselines[name]["location"]
            object_.rotation_euler = baselines[name]["rotation"]
            object_.scale = baselines[name]["scale"]
        for name, object_ in eye_parts.items():
            object_.scale = eye_scale_baselines[name]

        head = controls["CTRL_Head_Glance"]
        head.location = tuple(
            baselines["CTRL_Head_Glance"]["location"][index] + pose["head_offset"][index]
            for index in range(3)
        )
        head.rotation_euler = radians(pose["head_rotation"])
        controls["CTRL_Tail_Flick"].rotation_euler = radians(pose["tail_rotation"])
        controls["CTRL_Ear_L"].rotation_euler = radians(pose["ear_left"])
        controls["CTRL_Ear_R"].rotation_euler = radians(pose["ear_right"])
        controls["CTRL_Ear_L"].scale.z *= pose["ear_scale_z"]
        controls["CTRL_Ear_R"].scale.z *= pose["ear_scale_z"]
        for name in ("CTRL_Blink_L", "CTRL_Blink_R"):
            controls[name].scale.z = baselines[name]["scale"].z * pose["blink_scale"]
        for name, object_ in eye_parts.items():
            object_.scale.z = eye_scale_baselines[name].z * pose["blink_scale"]
        controls["CTRL_Laptop_Lid"].rotation_euler.x = math.radians(pose["lid_degrees"])

        path = states_dir / f"{pose['name']}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        entries.append(
            {
                "index": len(entries),
                "state": pose["name"],
                "lid_degrees": pose["lid_degrees"],
                "file": str(path.relative_to(output_dir)),
                "sha256": checksum(path),
                "bytes": path.stat().st_size,
            }
        )

    source = Path(bpy.data.filepath).resolve()
    repository_root = Path(__file__).resolve().parents[2]
    try:
        source_display = str(source.relative_to(repository_root))
    except ValueError:
        source_display = source.name
    manifest = {
        "schema_version": 1,
        "asset": "leo-the-dev",
        "status": "state-pose-candidate-not-runtime-approved",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "source": source_display,
            "source_sha256": checksum(source),
            "script": "tools/blender/render_state_poses.py",
        },
        "render": {
            "engine": scene.render.engine,
            "transparent": scene.render.film_transparent,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
        },
        "neutral": entries[0],
        "animation": {"name": "state-poses", "loop": False, "frames": entries},
        "identity_views": [],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_STATE_POSES={output_dir}")


if __name__ == "__main__":
    main()
