"""Render Leo's quadrupedal Walk and playful pounce-Run candidates."""

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
    {"name": "walk-right", "frames": 12, "frame_duration_ms": 125, "loop": True},
    {"name": "walk-left", "frames": 12, "frame_duration_ms": 125, "loop": True},
    {"name": "run-right", "frames": 12, "frame_duration_ms": 85, "loop": True},
    {"name": "run-left", "frames": 12, "frame_duration_ms": 85, "loop": True},
)

BODY_PARTS = (
    "Torso",
    "Chest",
    "Haunch_L",
    "Haunch_R",
    "Hind_Paw_L",
    "Hind_Paw_R",
    "Foreleg_L_Upper",
    "Foreleg_R_Upper",
    "Foreleg_L_Lower",
    "Foreleg_R_Lower",
    "Front_Paw_L",
    "Front_Paw_R",
)
CONTROL_NAMES = (
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--animations",
        default=",".join(animation["name"] for animation in ANIMATIONS),
        help="comma-separated animation names",
    )
    parser.add_argument(
        "--frame-indices",
        default="",
        help="optional comma-separated frame indices for visual iteration",
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


def keep_world_parent(child: bpy.types.Object, parent: bpy.types.Object) -> None:
    world = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


class LocomotionPose:
    def __init__(self) -> None:
        self.controls = {name: bpy.data.objects[name] for name in CONTROL_NAMES}
        self.parts = {name: bpy.data.objects[name] for name in BODY_PARTS}
        self.pose_objects = {**self.controls, **self.parts}
        self.baselines = {
            name: {
                "location": object_.location.copy(),
                "rotation": object_.rotation_euler.copy(),
                "scale": object_.scale.copy(),
            }
            for name, object_ in self.pose_objects.items()
        }
        for object_ in self.pose_objects.values():
            object_.animation_data_clear()

        self.body = self.controls["CTRL_Body_Breath"]
        self.head = self.controls["CTRL_Head_Glance"]
        self.tail = self.controls["CTRL_Tail_Flick"]
        self.lid = self.controls["CTRL_Laptop_Lid"]
        self.laptop = bpy.data.objects.new("POSE_Laptop_Carrier", None)
        bpy.context.collection.objects.link(self.laptop)
        self.laptop.location = (0.0, -1.37, 0.25)

        laptop_roots = [
            object_
            for object_ in bpy.data.objects
            if (object_.name.startswith("Laptop_") or object_.name == "CTRL_Laptop_Lid")
            and object_.parent is None
        ]
        for object_ in laptop_roots:
            keep_world_parent(object_, self.laptop)
        keep_world_parent(self.laptop, self.body)
        self.laptop_baseline = {
            "location": self.laptop.location.copy(),
            "rotation": self.laptop.rotation_euler.copy(),
            "scale": self.laptop.scale.copy(),
        }

        for name, length in (
            ("Head", 0.008),
            ("Torso", 0.010),
            ("Chest", 0.010),
            ("Haunch_L", 0.010),
            ("Haunch_R", 0.010),
        ):
            for modifier in bpy.data.objects[name].modifiers:
                if modifier.type == "PARTICLE_SYSTEM":
                    modifier.particle_system.settings.hair_length = length

    def reset(self) -> None:
        for name, object_ in self.pose_objects.items():
            baseline = self.baselines[name]
            object_.location = baseline["location"]
            object_.rotation_euler = baseline["rotation"]
            object_.scale = baseline["scale"]
        self.laptop.location = self.laptop_baseline["location"]
        self.laptop.rotation_euler = self.laptop_baseline["rotation"]
        self.laptop.scale = self.laptop_baseline["scale"]
        self.lid.rotation_euler.x = 0.0

    def set_part(
        self,
        name: str,
        location: tuple[float, float, float],
        rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        object_ = self.parts[name]
        object_.location = location
        object_.rotation_euler = radians(rotation)

    def base_quadruped(self, direction: str, body_height: float) -> None:
        camera = bpy.context.scene.camera
        camera_offset = camera.matrix_world.translation - self.body.matrix_world.translation
        camera_yaw = math.degrees(math.atan2(camera_offset.x, -camera_offset.y))
        turn = 70.0 if direction == "right" else -70.0
        body_baseline = self.baselines["CTRL_Body_Breath"]
        self.body.location = (
            body_baseline["location"].x,
            body_baseline["location"].y,
            body_baseline["location"].z + body_height,
        )
        self.body.rotation_euler = radians((0.0, 0.0, camera_yaw + turn))
        self.body.scale = (0.90, 0.90, 0.90)

        self.set_part("Torso", (0.0, 0.12, -0.25), (82.0, 0.0, 0.0))
        self.set_part("Chest", (0.0, -0.66, -0.28), (62.0, 0.0, 0.0))
        self.set_part("Haunch_L", (-0.58, 0.58, -0.68))
        self.set_part("Haunch_R", (0.58, 0.58, -0.68))

        self.head.location = (0.0, -1.04, 0.50)
        self.head.rotation_euler = radians((-6.0, 0.0, 0.0))
        self.controls["CTRL_Ear_L"].rotation_euler = radians((-4.0, 0.0, -4.0))
        self.controls["CTRL_Ear_R"].rotation_euler = radians((-4.0, 0.0, 4.0))
        self.tail.rotation_euler = radians((-8.0, 6.0, -6.0))

        bpy.context.view_layer.update()
        camera_local = self.body.matrix_world.inverted() @ camera.matrix_world.translation
        near_side = 0.82 if camera_local.x >= 0.0 else -0.82
        camera_up = camera.matrix_world.to_quaternion() @ Vector((0.0, 1.0, 0.0))
        body_axes = self.body.matrix_world.to_3x3()
        local_side = body_axes @ Vector((1.0, 0.0, 0.0))
        local_forward = body_axes @ Vector((0.0, 1.0, 0.0))
        local_up = body_axes @ Vector((0.0, 0.0, 1.0))
        self.ground_z_per_x = -camera_up.dot(local_side) / camera_up.dot(local_up)
        self.ground_z_per_y = -camera_up.dot(local_forward) / camera_up.dot(local_up)
        self.laptop.location = (near_side * 0.78, 0.38, -0.42)
        self.laptop.rotation_euler = radians((270.0, 0.0, 90.0))
        self.laptop.scale = (0.54, 0.54, 0.54)

    def place_limb(
        self,
        side: str,
        kind: str,
        forward: float,
        lift: float,
        swing: float,
    ) -> None:
        x = -0.46 if side == "L" else 0.46
        if kind == "front":
            self.set_part(
                f"Foreleg_{side}_Upper",
                (x, -0.58 + forward * 0.42, -0.35 + lift * 0.42),
                (-5.0 - swing * 17.0, 0.0, -2.0 if side == "L" else 2.0),
            )
            self.set_part(
                f"Foreleg_{side}_Lower",
                (x, -0.72 + forward * 0.72, -0.86 + lift * 0.72),
                (-swing * 12.0, 0.0, 0.0),
            )
            self.set_part(
                f"Front_Paw_{side}",
                (
                    x,
                    -0.86 + forward,
                    -1.36 + lift + x * self.ground_z_per_x + forward * self.ground_z_per_y,
                ),
                (4.0 - swing * 10.0, 0.0, 0.0),
            )
            return

        self.set_part(
            f"Haunch_{side}",
            (x * 1.24, 0.58 + forward * 0.25, -0.68 + lift * 0.18),
            (swing * 5.0, 0.0, 0.0),
        )
        self.set_part(
            f"Hind_Paw_{side}",
            (
                x * 1.18,
                0.48 + forward,
                -1.34 + lift + x * 1.18 * self.ground_z_per_x + forward * self.ground_z_per_y,
            ),
            (-3.0 - swing * 12.0, 0.0, 0.0),
        )

    def walk(self, phase: float, direction: str) -> None:
        wave = math.sin(phase * math.tau)
        self.base_quadruped(direction, 0.018 + 0.014 * math.sin(phase * math.tau * 2.0))
        limb_phases = {
            ("L", "hind"): 0.00,
            ("L", "front"): 0.25,
            ("R", "hind"): 0.50,
            ("R", "front"): 0.75,
        }
        for (side, kind), offset in limb_phases.items():
            limb_phase = (phase + offset) % 1.0
            angle = limb_phase * math.tau
            forward = 0.18 * math.cos(angle)
            lift = 0.15 * max(0.0, math.sin(angle)) ** 1.4
            self.place_limb(side, kind, forward, lift, math.sin(angle))
        self.head.location.z += 0.025 * math.sin(phase * math.tau * 2.0 + 0.4)
        self.head.rotation_euler.x += math.radians(1.5 * wave)
        self.tail.rotation_euler.z += math.radians(8.0 * wave)

    def run(self, phase: float, direction: str) -> None:
        launch = 0.5 + 0.5 * math.sin(phase * math.tau - math.pi / 2)
        airborne = smoothstep((launch - 0.18) / 0.58)
        compression = max(0.0, math.cos(phase * math.tau)) ** 6
        body_height = 0.02 + 0.30 * airborne - 0.08 * compression
        self.base_quadruped(direction, body_height)

        reach = math.sin(phase * math.tau)
        fore_forward = -0.52 * reach
        hind_forward = 0.46 * reach
        common_lift = 0.10 + 0.24 * airborne
        hind_drive = 0.10 * max(0.0, -reach)
        fore_drive = 0.08 * max(0.0, reach)
        for side in ("L", "R"):
            side_phase = 0.035 if side == "L" else -0.035
            self.place_limb(
                side,
                "front",
                fore_forward + side_phase,
                common_lift + fore_drive,
                reach,
            )
            self.place_limb(
                side,
                "hind",
                hind_forward - side_phase,
                common_lift + hind_drive,
                -reach,
            )
        torso = self.parts["Torso"]
        torso.scale.z = self.baselines["Torso"]["scale"].z * (1.0 + 0.08 * abs(reach))
        self.head.location.y -= 0.20 * reach
        self.head.location.z += 0.05 * airborne
        self.head.rotation_euler.x += math.radians(-4.0 * reach)
        self.controls["CTRL_Ear_L"].rotation_euler.x += math.radians(4.0 * airborne)
        self.controls["CTRL_Ear_R"].rotation_euler.x += math.radians(4.0 * airborne)
        self.tail.rotation_euler = radians((-12.0 + 7.0 * airborne, 8.0, -8.0 - 10.0 * reach))

    def apply(self, animation: str, phase: float) -> None:
        self.reset()
        gait, direction = animation.split("-", maxsplit=1)
        getattr(self, gait)(phase, direction)
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
    pose = LocomotionPose()

    selected_names = args.animations.split(",")
    animation_by_name = {animation["name"]: animation for animation in ANIMATIONS}
    if len(selected_names) != len(set(selected_names)) or any(
        name not in animation_by_name for name in selected_names
    ):
        raise ValueError(f"invalid animation selection: {selected_names}")
    selected = [animation_by_name[name] for name in selected_names]
    requested_indices = (
        [int(value) for value in args.frame_indices.split(",")] if args.frame_indices else None
    )

    animation_entries: list[dict[str, object]] = []
    for animation in selected:
        name = animation["name"]
        frame_count = animation["frames"]
        frames_dir = output_dir / "animations" / name
        frames_dir.mkdir(parents=True, exist_ok=True)
        frames: list[dict[str, object]] = []
        frame_indices = requested_indices if requested_indices is not None else range(frame_count)
        if any(index < 0 or index >= frame_count for index in frame_indices):
            raise ValueError(f"invalid frame selection for {name}: {list(frame_indices)}")
        for index in frame_indices:
            phase = index / frame_count
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
    manifest = {
        "schema_version": 1,
        "asset": "leo-the-dev",
        "status": "locomotion-candidate-not-runtime-approved",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "source": source_display,
            "source_sha256": checksum(source),
            "script": "tools/blender/render_locomotion.py",
        },
        "render": {
            "engine": scene.render.engine,
            "transparent": scene.render.film_transparent,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
        },
        "neutral": animation_entries[0]["frames"][0],
        "animations": animation_entries,
        "identity_views": [],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_LOCOMOTION={output_dir}")


if __name__ == "__main__":
    main()
