"""Render Leo's seated Wave and four-paw Jump candidates."""

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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_locomotion import LocomotionPose, radians  # noqa: E402

ANIMATIONS: tuple[dict[str, Any], ...] = (
    {"name": "wave", "frames": 10, "frame_duration_ms": 150, "loop": False},
    {"name": "jump", "frames": 12, "frame_duration_ms": 110, "loop": False},
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


def pulse(phase: float, start: float, end: float) -> float:
    if phase <= start or phase >= end:
        return 0.0
    return math.sin(math.pi * (phase - start) / (end - start))


class GesturePose:
    def __init__(self) -> None:
        self.leo = LocomotionPose()
        for name in ("Foreleg_R_Upper", "Foreleg_R_Lower", "Front_Paw_R"):
            for modifier in bpy.data.objects[name].modifiers:
                if modifier.type == "PARTICLE_SYSTEM":
                    modifier.particle_system.settings.hair_length = 0.008

    def wave(self, phase: float) -> None:
        leo = self.leo
        leo.reset()
        envelope = math.sin(math.pi * phase)
        paw_wave = math.sin(phase * math.tau * 2.0) * envelope

        upper = leo.parts["Foreleg_R_Upper"]
        lower = leo.parts["Foreleg_R_Lower"]
        paw = leo.parts["Front_Paw_R"]
        upper_baseline = leo.baselines["Foreleg_R_Upper"]
        lower_baseline = leo.baselines["Foreleg_R_Lower"]
        paw_baseline = leo.baselines["Front_Paw_R"]

        upper.location = (
            upper_baseline["location"].x + 0.12 * envelope,
            upper_baseline["location"].y - 0.08 * envelope,
            upper_baseline["location"].z + 0.52 * envelope,
        )
        upper.rotation_euler = radians((-5.0 - 18.0 * envelope, 0.0, 2.0 - 18.0 * envelope))
        lower.location = (
            lower_baseline["location"].x + 0.27 * envelope,
            lower_baseline["location"].y - 0.22 * envelope,
            lower_baseline["location"].z + 1.14 * envelope,
        )
        lower.rotation_euler = radians((-26.0 * envelope, 0.0, -30.0 * envelope))
        paw.location = (
            paw_baseline["location"].x + 0.44 * envelope + 0.16 * paw_wave,
            paw_baseline["location"].y - 0.30 * envelope,
            paw_baseline["location"].z + 1.88 * envelope,
        )
        paw.rotation_euler = radians((14.0 * envelope, -8.0 * envelope, -20.0 * paw_wave))

        leo.head.rotation_euler = radians((-2.0 * envelope, 1.5 * envelope, -7.0 * envelope))
        leo.controls["CTRL_Ear_L"].rotation_euler = radians((-2.0, 0.0, -4.0))
        leo.controls["CTRL_Ear_R"].rotation_euler = radians((-4.0, 0.0, 5.0 + 2.0 * paw_wave))
        leo.tail.rotation_euler = radians((0.0, 0.0, -2.0 + 7.0 * paw_wave))
        leo.lid.rotation_euler.x = 0.0

    def jump(self, phase: float) -> None:
        leo = self.leo
        leo.reset()
        if phase <= 0.0 or phase >= 1.0:
            air = 0.0
            extension = 0.0
        else:
            air = math.sin(math.pi * phase) ** 1.35
            extension = math.sin(phase * math.tau) * air
        compression = pulse(phase, 0.0, 0.27) + 0.82 * pulse(phase, 0.70, 1.0)
        body_height = 0.40 * air - 0.075 * compression
        leo.base_quadruped("right", body_height)

        front_forward = -0.30 * extension + 0.08 * compression
        hind_forward = 0.27 * extension - 0.07 * compression
        limb_lift = 0.16 * air + 0.05 * compression
        for side, side_offset in (("L", 0.025), ("R", -0.025)):
            leo.place_limb(
                side,
                "front",
                front_forward + side_offset * air,
                limb_lift,
                extension,
            )
            leo.place_limb(
                side,
                "hind",
                hind_forward - side_offset * air,
                limb_lift,
                -extension,
            )

        leo.head.location.y -= 0.12 * extension
        leo.head.location.z += 0.07 * air - 0.035 * compression
        leo.head.rotation_euler.x += math.radians(-5.0 * extension + 3.0 * compression)
        leo.controls["CTRL_Ear_L"].rotation_euler.x += math.radians(4.0 * air)
        leo.controls["CTRL_Ear_R"].rotation_euler.x += math.radians(4.0 * air)
        leo.tail.rotation_euler = radians((-10.0 + 7.0 * air, 7.0, -8.0 - 9.0 * extension))

    def apply(self, animation: str, phase: float) -> None:
        effective_phase = 0.0 if phase >= 1.0 else phase
        getattr(self, animation)(effective_phase)
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
    pose = GesturePose()

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
            phase = index / (frame_count - 1)
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
        frame_by_index = {frame["index"]: frame for frame in frames}
        if 0 in frame_by_index and frame_count - 1 in frame_by_index:
            first_path = output_dir / frame_by_index[0]["file"]
            last_entry = frame_by_index[frame_count - 1]
            last_path = output_dir / last_entry["file"]
            shutil.copyfile(first_path, last_path)
            last_entry["sha256"] = checksum(last_path)
            last_entry["bytes"] = last_path.stat().st_size
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
        "status": "gesture-candidate-not-runtime-approved",
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "source": source_display,
            "source_sha256": checksum(source),
            "script": "tools/blender/render_gestures.py",
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
    print(f"LEO_GESTURES={output_dir}")


if __name__ == "__main__":
    main()
