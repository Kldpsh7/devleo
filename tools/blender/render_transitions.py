"""Render Leo's seated Idle to quadrupedal Walk transition candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import bpy
from mathutils import Matrix, Vector

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_locomotion import LocomotionPose  # noqa: E402

ANIMATIONS: tuple[dict[str, Any], ...] = (
    {"name": "idle-to-walk-right", "frames": 20, "frame_duration_ms": 70, "loop": False},
    {"name": "walk-right-to-idle", "frames": 20, "frame_duration_ms": 70, "loop": False},
    {"name": "idle-to-walk-left", "frames": 20, "frame_duration_ms": 70, "loop": False},
    {"name": "walk-left-to-idle", "frames": 20, "frame_duration_ms": 70, "loop": False},
)
LAPTOP_CENTER_LOCAL = Vector((0.0, -1.37, 0.25))


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


def smootherstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value**3 * (value * (value * 6.0 - 15.0) + 10.0)


def angle_lerp(start: float, end: float, amount: float) -> float:
    difference = (end - start + math.pi) % math.tau - math.pi
    return start + difference * amount


class TransitionPose:
    def __init__(self) -> None:
        self.leo = LocomotionPose()
        self.objects = {**self.leo.pose_objects, "POSE_Laptop_Carrier": self.leo.laptop}
        self.leo.reset()
        self.idle = self.capture()
        self.idle_laptop_world = self.capture_laptop_world()
        self.walk: dict[str, dict[str, dict[str, tuple[float, float, float]]]] = {}
        self.walk_laptop_world: dict[str, dict[str, object]] = {}
        for direction in ("right", "left"):
            self.leo.apply(f"walk-{direction}", 0.0)
            self.walk[direction] = self.capture()
            self.walk_laptop_world[direction] = self.capture_laptop_world()
        camera_rotation = bpy.context.scene.camera.matrix_world.to_quaternion()
        self.camera_right = camera_rotation @ Vector((1.0, 0.0, 0.0))
        self.camera_up = camera_rotation @ Vector((0.0, 1.0, 0.0))
        self.apply("right", 0.0)

    def capture(self) -> dict[str, dict[str, tuple[float, float, float]]]:
        return {
            name: {
                "location": tuple(object_.location),
                "rotation": tuple(object_.rotation_euler),
                "scale": tuple(object_.scale),
            }
            for name, object_ in self.objects.items()
        }

    def capture_laptop_world(self) -> dict[str, object]:
        location, rotation, scale = self.leo.laptop.matrix_world.decompose()
        return {
            "location": location.copy(),
            "rotation": rotation.copy(),
            "scale": scale.copy(),
            "center": (self.leo.laptop.matrix_world @ LAPTOP_CENTER_LOCAL).copy(),
        }

    def apply_snapshot(
        self,
        source: dict[str, dict[str, tuple[float, float, float]]],
        target: dict[str, dict[str, tuple[float, float, float]]],
        amount: float,
    ) -> None:
        for name, object_ in self.objects.items():
            if name == "POSE_Laptop_Carrier":
                continue
            source_pose = source[name]
            target_pose = target[name]
            object_.location = tuple(
                start + (end - start) * amount
                for start, end in zip(source_pose["location"], target_pose["location"], strict=True)
            )
            object_.rotation_euler = tuple(
                angle_lerp(start, end, amount)
                for start, end in zip(source_pose["rotation"], target_pose["rotation"], strict=True)
            )
            object_.scale = tuple(
                start + (end - start) * amount
                for start, end in zip(source_pose["scale"], target_pose["scale"], strict=True)
            )

    def place_laptop(self, direction: str, amount: float, phase: float) -> Vector:
        source = self.idle_laptop_world
        target = self.walk_laptop_world[direction]
        rotation = source["rotation"].slerp(target["rotation"], amount)
        scale = source["scale"].lerp(target["scale"], amount)
        center = source["center"].lerp(target["center"], amount)
        outward_sign = -1.0 if direction == "right" else 1.0
        outward_distance = 0.30 if direction == "right" else 0.46
        center += self.camera_right * outward_sign * outward_distance * math.sin(math.pi * phase)
        scaled_local_center = Vector(
            tuple(coordinate * scale[index] for index, coordinate in enumerate(LAPTOP_CENTER_LOCAL))
        )
        carrier_location = center - rotation @ scaled_local_center
        self.leo.laptop.matrix_world = Matrix.LocRotScale(carrier_location, rotation, scale)
        return center

    def place_carrying_leg(self, direction: str, laptop_center: Vector, phase: float) -> None:
        side = "L" if direction == "right" else "R"
        upper = self.leo.parts[f"Foreleg_{side}_Upper"]
        lower = self.leo.parts[f"Foreleg_{side}_Lower"]
        paw = self.leo.parts[f"Front_Paw_{side}"]
        matrices = {object_: object_.matrix_world.copy() for object_ in (upper, lower, paw)}
        inner_sign = 1.0 if direction == "right" else -1.0
        contact = laptop_center - self.camera_up * 0.25 + self.camera_right * inner_sign * 0.13
        grip = math.sin(math.pi * phase) ** 0.82
        delta = contact - matrices[paw].translation
        for object_, influence in ((upper, 0.18), (lower, 0.52), (paw, 0.92)):
            matrix = matrices[object_]
            matrix.translation += delta * influence * grip
            object_.matrix_world = matrix

    def apply(self, direction: str, phase: float) -> None:
        amount = smootherstep(phase)
        self.apply_snapshot(self.idle, self.walk[direction], amount)
        bpy.context.view_layer.update()
        laptop_center = self.place_laptop(direction, amount, phase)

        # A short crouch and lift make the change read as Leo scooping up the
        # laptop and turning onto four paws instead of morphing between poses.
        if 0.0 < phase < 1.0:
            anticipation = math.sin(math.pi * phase)
            self.leo.body.location.z -= 0.055 * anticipation
            self.leo.head.location.y -= 0.07 * anticipation
            self.leo.head.rotation_euler.x += math.radians(4.0 * anticipation)
            tail_direction = -1.0 if direction == "right" else 1.0
            self.leo.tail.rotation_euler.z += math.radians(tail_direction * 7.0 * anticipation)
            bpy.context.view_layer.update()
            self.place_carrying_leg(direction, laptop_center, phase)
        bpy.context.view_layer.update()


def frame_entry(index: int, path: Path, output_dir: Path) -> dict[str, object]:
    return {
        "index": index,
        "file": str(path.relative_to(output_dir)),
        "sha256": checksum(path),
        "bytes": path.stat().st_size,
    }


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.frame_set(scene.frame_start)
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    pose = TransitionPose()

    animation_by_name = {animation["name"]: animation for animation in ANIMATIONS}
    rendered_frames: dict[str, list[dict[str, object]]] = {}
    for direction in ("right", "left"):
        name = f"idle-to-walk-{direction}"
        animation = animation_by_name[name]
        frame_count = animation["frames"]
        frames_dir = output_dir / "animations" / name
        frames_dir.mkdir(parents=True, exist_ok=True)
        frames: list[dict[str, object]] = []
        for index in range(frame_count):
            phase = index / (frame_count - 1)
            pose.apply(direction, phase)
            path = frames_dir / f"{index:02d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frames.append(frame_entry(index, path, output_dir))
        rendered_frames[name] = frames

    # Both departure directions share the canonical Idle endpoint. Reusing its
    # pixels avoids hair antialias noise being mistaken for a visual snap.
    shared_idle = output_dir / rendered_frames["idle-to-walk-right"][0]["file"]
    left_idle_entry = rendered_frames["idle-to-walk-left"][0]
    left_idle = output_dir / left_idle_entry["file"]
    shutil.copyfile(shared_idle, left_idle)
    left_idle_entry.update(frame_entry(0, left_idle, output_dir))

    for direction in ("right", "left"):
        forward_name = f"idle-to-walk-{direction}"
        reverse_name = f"walk-{direction}-to-idle"
        reverse_dir = output_dir / "animations" / reverse_name
        reverse_dir.mkdir(parents=True, exist_ok=True)
        reverse_frames: list[dict[str, object]] = []
        for index, source_entry in enumerate(reversed(rendered_frames[forward_name])):
            source_path = output_dir / source_entry["file"]
            destination = reverse_dir / f"{index:02d}.png"
            shutil.copyfile(source_path, destination)
            reverse_frames.append(frame_entry(index, destination, output_dir))
        rendered_frames[reverse_name] = reverse_frames

    animation_entries = [
        {**animation, "frames": rendered_frames[animation["name"]]} for animation in ANIMATIONS
    ]
    source = Path(bpy.data.filepath).resolve()
    repository_root = Path(__file__).resolve().parents[2]
    try:
        source_display = str(source.relative_to(repository_root))
    except ValueError:
        source_display = source.name
    manifest = {
        "schema_version": 1,
        "asset": "leo-the-dev",
        "status": "transition-candidate-not-runtime-approved",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "source": source_display,
            "source_sha256": checksum(source),
            "script": "tools/blender/render_transitions.py",
        },
        "render": {
            "engine": scene.render.engine,
            "transparent": scene.render.film_transparent,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
        },
        "neutral": rendered_frames["idle-to-walk-right"][0],
        "animations": animation_entries,
        "identity_views": [],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_TRANSITIONS={output_dir}")


if __name__ == "__main__":
    main()
