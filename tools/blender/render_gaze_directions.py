"""Render Leo's cardinal or complete 16-direction gaze family."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import bpy
from mathutils import Vector

DIRECTIONS: tuple[tuple[str, float, str], ...] = (
    ("000", 0.0, "up"),
    ("022.5", 22.5, "up-right"),
    ("045", 45.0, "up-right"),
    ("067.5", 67.5, "up-right"),
    ("090", 90.0, "right"),
    ("112.5", 112.5, "down-right"),
    ("135", 135.0, "down-right"),
    ("157.5", 157.5, "down-right"),
    ("180", 180.0, "down"),
    ("202.5", 202.5, "down-left"),
    ("225", 225.0, "down-left"),
    ("247.5", 247.5, "down-left"),
    ("270", 270.0, "left"),
    ("292.5", 292.5, "up-left"),
    ("315", 315.0, "up-left"),
    ("337.5", 337.5, "up-left"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--directions",
        default=",".join(label for label, _, _ in DIRECTIONS),
        help="comma-separated direction labels",
    )
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


class GazePose:
    def __init__(self) -> None:
        names = (
            "CTRL_Body_Breath",
            "CTRL_Head_Glance",
            "CTRL_Tail_Flick",
            "CTRL_Ear_L",
            "CTRL_Ear_R",
            "CTRL_Blink_L",
            "CTRL_Blink_R",
            "CTRL_Eye_Gaze_L",
            "CTRL_Eye_Gaze_R",
            "CTRL_Laptop_Lid",
        )
        self.controls = {name: bpy.data.objects[name] for name in names}
        self.baselines = {
            name: {
                "location": object_.location.copy(),
                "rotation": object_.rotation_euler.copy(),
                "scale": object_.scale.copy(),
            }
            for name, object_ in self.controls.items()
        }
        eye_surface_names = (
            "Iris_L",
            "Iris_R",
            "Pupil_L",
            "Pupil_R",
            "Eye_Glint_L",
            "Eye_Glint_R",
        )
        self.eye_surfaces = {name: bpy.data.objects[name] for name in eye_surface_names}
        self.eye_surface_baselines = {
            name: {
                "location": object_.location.copy(),
                "rotation": object_.rotation_euler.copy(),
                "scale": object_.scale.copy(),
            }
            for name, object_ in self.eye_surfaces.items()
        }

    def reset(self) -> None:
        for name, object_ in self.controls.items():
            baseline = self.baselines[name]
            object_.location = baseline["location"]
            object_.rotation_euler = baseline["rotation"]
            object_.scale = baseline["scale"]
        for name, object_ in self.eye_surfaces.items():
            baseline = self.eye_surface_baselines[name]
            object_.location = baseline["location"]
            object_.rotation_euler = baseline["rotation"]
            object_.scale = baseline["scale"]
        self.controls["CTRL_Laptop_Lid"].rotation_euler.x = 0.0
        self.controls["CTRL_Tail_Flick"].rotation_euler = radians((0.0, 0.0, -2.0))

    def apply(self, degrees: float) -> None:
        self.reset()
        angle = math.radians(degrees)
        screen_x = math.sin(angle)
        screen_up = math.cos(angle)

        head = self.controls["CTRL_Head_Glance"]
        head_baseline = self.baselines["CTRL_Head_Glance"]
        camera = bpy.context.scene.camera
        camera_offset = camera.matrix_world.translation - head.matrix_world.translation
        camera_yaw = math.degrees(math.atan2(camera_offset.x, -camera_offset.y))
        head.location = (
            head_baseline["location"].x + 0.045 * screen_x,
            head_baseline["location"].y,
            head_baseline["location"].z + 0.040 * screen_up,
        )
        head.rotation_euler = radians(
            (-32.0 * screen_up, 2.5 * screen_x * screen_up, camera_yaw + 46.0 * screen_x)
        )

        bpy.context.view_layer.update()
        camera_rotation = camera.matrix_world.to_quaternion()
        camera_right = camera_rotation @ Vector((1.0, 0.0, 0.0))
        camera_up = camera_rotation @ Vector((0.0, 1.0, 0.0))
        for object_ in self.eye_surfaces.values():
            matrix = object_.matrix_world.copy()
            matrix.translation += camera_right * (0.075 * screen_x)
            matrix.translation += camera_up * (0.075 * screen_up)
            object_.matrix_world = matrix

        left_ear = self.controls["CTRL_Ear_L"]
        right_ear = self.controls["CTRL_Ear_R"]
        left_ear.rotation_euler = radians(
            (-2.5 * screen_up, 0.0, -2.0 * screen_x - 1.0 * screen_up)
        )
        right_ear.rotation_euler = radians(
            (-2.5 * screen_up, 0.0, 2.0 * screen_x + 1.0 * screen_up)
        )
        self.controls["CTRL_Tail_Flick"].rotation_euler = radians((0.0, 0.0, -2.0 - 1.5 * screen_x))
        bpy.context.view_layer.update()


def render_entry(scene: bpy.types.Scene, path: Path) -> dict[str, object]:
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return {
        "file": str(path),
        "sha256": checksum(path),
        "bytes": path.stat().st_size,
    }


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    directions_dir = output_dir / "directions"
    directions_dir.mkdir(parents=True, exist_ok=True)
    requested = args.directions.split(",")
    direction_by_label = {label: (degrees, expected) for label, degrees, expected in DIRECTIONS}
    if len(requested) != len(set(requested)) or any(
        label not in direction_by_label for label in requested
    ):
        raise ValueError(f"invalid direction selection: {requested}")

    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    pose = GazePose()
    pose.reset()
    bpy.context.view_layer.update()

    neutral_path = output_dir / "neutral.png"
    neutral = render_entry(scene, neutral_path)
    neutral["file"] = neutral_path.name

    entries: list[dict[str, object]] = []
    for index, label in enumerate(requested):
        degrees, expected = direction_by_label[label]
        pose.apply(degrees)
        path = directions_dir / f"{index:02d}-{label}.png"
        rendered = render_entry(scene, path)
        rendered["file"] = str(path.relative_to(output_dir))
        entries.append(
            {
                "index": index,
                "direction": label,
                "degrees": degrees,
                "expected": expected,
                **rendered,
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
        "status": "gaze-candidate-not-runtime-approved",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "source": source_display,
            "source_sha256": checksum(source),
            "script": "tools/blender/render_gaze_directions.py",
        },
        "render": {
            "engine": scene.render.engine,
            "transparent": scene.render.film_transparent,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
        },
        "neutral": neutral,
        "animation": {
            "name": "gaze-directions",
            "loop": len(entries) == 16,
            "frame_duration_ms": 220,
            "frames": entries,
        },
        "identity_views": [],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_GAZE_DIRECTIONS={output_dir}")


if __name__ == "__main__":
    main()
