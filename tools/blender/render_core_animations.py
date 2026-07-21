"""Render Leo's Waiting, Working, Review, and Failure animation candidates."""

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
from mathutils import Vector

ANIMATIONS: tuple[dict[str, Any], ...] = (
    {"name": "waiting", "frames": 12, "frame_duration_ms": 210, "loop": True},
    {"name": "working", "frames": 16, "frame_duration_ms": 145, "loop": True},
    {"name": "review", "frames": 12, "frame_duration_ms": 210, "loop": True},
    {"name": "failure", "frames": 14, "frame_duration_ms": 140, "loop": False},
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


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def blink_scale(phase: float, center: float, width: float = 0.09) -> float:
    distance = min(abs(phase - center), 1.0 - abs(phase - center))
    return 0.08 + 0.92 * smoothstep(min(1.0, distance / width))


class LeoPose:
    def __init__(self) -> None:
        control_names = (
            "CTRL_Body_Breath",
            "CTRL_Head_Glance",
            "CTRL_Tail_Flick",
            "CTRL_Ear_L",
            "CTRL_Ear_R",
            "CTRL_Blink_L",
            "CTRL_Blink_R",
            "CTRL_Laptop_Lid",
        )
        self.controls = {name: bpy.data.objects[name] for name in control_names}
        self.control_baselines = {
            name: {
                "location": object_.location.copy(),
                "rotation": object_.rotation_euler.copy(),
                "scale": object_.scale.copy(),
            }
            for name, object_ in self.controls.items()
        }
        eye_names = (
            "Eye_L",
            "Eye_R",
            "Iris_L",
            "Iris_R",
            "Pupil_L",
            "Pupil_R",
            "Eye_Glint_L",
            "Eye_Glint_R",
        )
        self.eye_parts = {name: bpy.data.objects[name] for name in eye_names}
        self.eye_scale_baselines = {
            name: object_.scale.copy() for name, object_ in self.eye_parts.items()
        }
        self.paws = {name: bpy.data.objects[name] for name in ("Front_Paw_L", "Front_Paw_R")}
        self.paw_location_baselines = {
            name: object_.location.copy() for name, object_ in self.paws.items()
        }
        self.tail = bpy.data.objects["Tail"]
        self.tail_points = [point.co.copy() for point in self.tail.data.splines[0].bezier_points]
        self.tail_tuft = bpy.data.objects["Tail_Tuft"]
        self.tail_tuft_baseline = self.tail_tuft.matrix_world.copy()

    def reset(self) -> None:
        for name, object_ in self.controls.items():
            baseline = self.control_baselines[name]
            object_.location = baseline["location"]
            object_.rotation_euler = baseline["rotation"]
            object_.scale = baseline["scale"]
        for name, object_ in self.eye_parts.items():
            object_.scale = self.eye_scale_baselines[name]
        for name, object_ in self.paws.items():
            object_.location = self.paw_location_baselines[name]
        for point, coordinate in zip(
            self.tail.data.splines[0].bezier_points, self.tail_points, strict=True
        ):
            point.co = coordinate
        self.tail_tuft.matrix_world = self.tail_tuft_baseline

    def set_head(
        self,
        rotation: tuple[float, float, float],
        offset: tuple[float, float, float],
    ) -> None:
        head = self.controls["CTRL_Head_Glance"]
        baseline = self.control_baselines["CTRL_Head_Glance"]
        head.location = tuple(baseline["location"][index] + offset[index] for index in range(3))
        head.rotation_euler = radians(rotation)

    def set_ears(
        self,
        left: tuple[float, float, float],
        right: tuple[float, float, float],
        scale_z: float = 1.0,
    ) -> None:
        for name, rotation in (("CTRL_Ear_L", left), ("CTRL_Ear_R", right)):
            self.controls[name].rotation_euler = radians(rotation)
            self.controls[name].scale.z = self.control_baselines[name]["scale"].z * scale_z

    def set_blink(self, scale_z: float) -> None:
        for name in ("CTRL_Blink_L", "CTRL_Blink_R"):
            self.controls[name].scale.z = self.control_baselines[name]["scale"].z * scale_z
        for name, object_ in self.eye_parts.items():
            object_.scale.z = self.eye_scale_baselines[name].z * scale_z

    def set_lid(self, degrees: float) -> None:
        self.controls["CTRL_Laptop_Lid"].rotation_euler.x = math.radians(degrees)

    def set_breath(self, amount: float) -> None:
        body = self.controls["CTRL_Body_Breath"]
        baseline = self.control_baselines["CTRL_Body_Breath"]["scale"]
        body.scale = (baseline.x + amount * 0.25, baseline.y + amount * 0.25, baseline.z + amount)

    def set_tail_path(self, points: tuple[tuple[float, float, float], ...]) -> None:
        for point, coordinate in zip(self.tail.data.splines[0].bezier_points, points, strict=True):
            point.co = coordinate
        matrix = self.tail_tuft.matrix_world.copy()
        matrix.translation = Vector(points[-1])
        self.tail_tuft.matrix_world = matrix

    def set_paw_offsets(self, left_z: float, right_z: float) -> None:
        for name, z_offset in (("Front_Paw_L", left_z), ("Front_Paw_R", right_z)):
            baseline = self.paw_location_baselines[name]
            self.paws[name].location = (
                baseline.x,
                baseline.y - z_offset * 0.7,
                baseline.z + z_offset,
            )

    def waiting(self, phase: float) -> None:
        wave = math.sin(phase * math.tau)
        self.set_lid(48.0)
        self.set_breath(0.008 * wave)
        self.set_head((-2.0 + wave, 1.0, 9.0 + 2.0 * wave), (0.0, 0.0, 0.02))
        self.set_ears((-3.0, 0.0, -5.0 - wave), (1.0, 0.0, 3.0 + wave))
        self.set_blink(blink_scale(phase, 0.67))
        self.controls["CTRL_Tail_Flick"].rotation_euler = radians((2.0, 0.0, 4.0 + 4.0 * wave))

    def working(self, phase: float) -> None:
        wave = math.sin(phase * math.tau)
        tap = 0.5 + 0.5 * math.sin(phase * math.tau * 2.0)
        self.set_lid(96.0)
        self.set_breath(0.006 * wave)
        self.set_head((10.5 + 1.1 * wave, 0.0, -1.0 + 0.8 * wave), (0.0, -0.02, -0.05))
        self.set_ears((1.5, 0.0, -1.5), (1.5, 0.0, 1.5))
        self.set_blink(blink_scale(phase, 0.73, width=0.07))
        self.set_paw_offsets(0.025 * tap, 0.025 * (1.0 - tap))
        tip = (0.88 + 0.05 * wave, -1.72, 0.30 + 0.075 * tap)
        self.set_tail_path(
            (
                (0.69, 0.36, 1.24),
                (1.16, 0.18, 1.06),
                (1.47, -0.42, 0.80),
                (1.35, -1.12, 0.49),
                tip,
            )
        )

    def review(self, phase: float) -> None:
        wave = math.sin(phase * math.tau)
        left_twitch = math.sin(phase * math.tau * 2.0)
        right_twitch = math.sin(phase * math.tau * 2.0 + math.pi)
        swipe = 0.5 + 0.5 * wave
        self.set_lid(96.0)
        self.set_breath(0.004 * wave)
        self.set_head((9.0, -1.5, -4.0 + wave), (-0.02, -0.01, -0.04))
        self.set_ears(
            (-2.5 + 3.0 * left_twitch, 0.0, -3.0),
            (2.0 + 3.0 * right_twitch, 0.0, 4.0),
            scale_z=0.92,
        )
        self.set_blink(0.55 + 0.06 * wave)
        self.set_paw_offsets(0.0, 0.018 * swipe)
        tip = (0.60 + 0.48 * swipe, -1.70, 0.34)
        self.set_tail_path(
            (
                (0.69, 0.36, 1.24),
                (1.18, 0.14, 1.04),
                (1.50, -0.48, 0.76),
                (1.35, -1.10, 0.47),
                tip,
            )
        )

    def failure(self, phase: float) -> None:
        ear_progress = smoothstep(phase / 0.28)
        head_progress = smoothstep((phase - 0.18) / 0.64)
        eye_progress = smoothstep((phase - 0.20) / 0.40)
        self.set_lid(0.0)
        self.set_head(
            (34.0 * head_progress, 0.0, 0.0),
            (0.0, -0.40 * head_progress, -2.62 * head_progress),
        )
        self.set_ears(
            (45.0 * ear_progress, 0.0, 4.0 * ear_progress),
            (45.0 * ear_progress, 0.0, -4.0 * ear_progress),
            scale_z=1.0 - 0.48 * ear_progress,
        )
        self.set_blink(1.0 - 0.92 * eye_progress)
        self.controls["CTRL_Tail_Flick"].rotation_euler = radians(
            (-5.0 * head_progress, 0.0, -2.0 - 7.0 * head_progress)
        )

    def apply(self, animation: str, phase: float) -> None:
        self.reset()
        getattr(self, animation)(phase)
        bpy.context.view_layer.update()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    pose = LeoPose()

    animation_entries: list[dict[str, object]] = []
    for animation in ANIMATIONS:
        name = animation["name"]
        frame_count = animation["frames"]
        frames_dir = output_dir / "animations" / name
        frames_dir.mkdir(parents=True, exist_ok=True)
        frames: list[dict[str, object]] = []
        for index in range(frame_count):
            phase = index / frame_count if animation["loop"] else index / (frame_count - 1)
            pose.apply(name, phase)
            path = frames_dir / f"{index:02d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frames.append(
                {
                    "index": index,
                    "file": str(path.relative_to(output_dir)),
                    "sha256": checksum(path),
                    "bytes": path.stat().st_size,
                }
            )
        animation_entries.append({**animation, "frames": frames})

    source = Path(bpy.data.filepath).resolve()
    repository_root = Path(__file__).resolve().parents[2]
    try:
        source_display = str(source.relative_to(repository_root))
    except ValueError:
        source_display = source.name
    first_frame = animation_entries[0]["frames"][0]
    manifest = {
        "schema_version": 1,
        "asset": "leo-the-dev",
        "status": "core-animation-candidate-not-runtime-approved",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "source": source_display,
            "source_sha256": checksum(source),
            "script": "tools/blender/render_core_animations.py",
        },
        "render": {
            "engine": scene.render.engine,
            "transparent": scene.render.film_transparent,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
        },
        "neutral": first_frame,
        "animations": animation_entries,
        "identity_views": [],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_CORE_ANIMATIONS={output_dir}")


if __name__ == "__main__":
    main()
