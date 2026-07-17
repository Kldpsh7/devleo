"""Render Leo's neutral frame and 12-frame Idle prototype from a .blend scene."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=64)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def disable_render_stamps(scene: bpy.types.Scene) -> None:
    scene.render.use_stamp = False
    for attribute in (
        "use_stamp_camera",
        "use_stamp_date",
        "use_stamp_filename",
        "use_stamp_frame",
        "use_stamp_hostname",
        "use_stamp_lens",
        "use_stamp_marker",
        "use_stamp_memory",
        "use_stamp_note",
        "use_stamp_render_time",
        "use_stamp_scene",
        "use_stamp_time",
    ):
        if hasattr(scene.render, attribute):
            setattr(scene.render, attribute, False)


def look_at(object_: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - object_.location
    object_.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def validate_scene(scene: bpy.types.Scene) -> dict[str, object]:
    required_objects = {
        "RIG_Leo",
        "Head",
        "Torso",
        "Chest",
        "Muzzle_L",
        "Muzzle_R",
        "Eye_L",
        "Eye_R",
        "Iris_L",
        "Iris_R",
        "Tail",
        "Tail_Tuft",
        "Laptop_Closed_Lid",
        "Laptop_Dark_Rim",
        "Laptop_Hinge",
        "Leo Camera",
        "Key softbox",
        "Fill softbox",
        "Rim softbox",
    }
    required_bones = {
        "root",
        "pelvis",
        "spine",
        "neck",
        "head",
        "foreleg_upper.L",
        "foreleg_lower.L",
        "front_paw.L",
        "hind_thigh.L",
        "hind_paw.L",
        "foreleg_upper.R",
        "foreleg_lower.R",
        "front_paw.R",
        "hind_thigh.R",
        "hind_paw.R",
        "tail.01",
        "tail.02",
        "tail.03",
        "prop_laptop",
    }
    missing_objects = sorted(required_objects - set(bpy.data.objects.keys()))
    rig = bpy.data.objects.get("RIG_Leo")
    bone_names = set(rig.data.bones.keys()) if rig is not None and rig.type == "ARMATURE" else set()
    missing_bones = sorted(required_bones - bone_names)
    fur_system_count = sum(
        len(object_.particle_systems) for object_ in bpy.data.objects if object_.type == "MESH"
    )
    lid = bpy.data.objects.get("Laptop_Closed_Lid")
    lid_dimensions = [round(value, 3) for value in lid.dimensions] if lid is not None else []
    result: dict[str, object] = {
        "ok": not missing_objects and not missing_bones and fur_system_count >= 18,
        "asset_status": scene.get("leo_asset_status"),
        "missing_objects": missing_objects,
        "missing_bones": missing_bones,
        "rig_bone_count": len(bone_names),
        "fur_system_count": fur_system_count,
        "laptop_lid_dimensions": lid_dimensions,
        "light_count": sum(1 for object_ in bpy.data.objects if object_.type == "LIGHT"),
    }
    return result


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    idle_dir = output_dir / "idle"
    idle_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    if scene.get("leo_pipeline_version") != 1:
        raise RuntimeError("The loaded file is not a supported Leo source scene")
    scene_validation = validate_scene(scene)
    if not scene_validation["ok"]:
        raise RuntimeError(f"Leo source scene validation failed: {scene_validation}")
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    disable_render_stamps(scene)
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = args.samples

    scene.frame_set(scene.frame_start)
    neutral_path = output_dir / "neutral.png"
    scene.render.filepath = str(neutral_path)
    bpy.ops.render.render(write_still=True)

    if scene.camera is None:
        raise RuntimeError("The Leo source scene has no render camera")
    identity_dir = output_dir / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    camera = scene.camera
    original_matrix = camera.matrix_world.copy()
    original_ortho_scale = camera.data.ortho_scale
    identity_views: list[dict[str, object]] = []
    for name, location, target, ortho_scale in (
        ("front", (0.0, -14.0, 5.8), (0.0, -0.42, 2.18), 5.65),
        ("three-quarter", (4.55, -12.8, 6.25), (0.0, -0.42, 2.20), 5.55),
        ("profile", (13.8, -0.42, 5.8), (0.0, -0.42, 2.18), 5.90),
    ):
        camera.location = location
        camera.data.ortho_scale = ortho_scale
        look_at(camera, target)
        path = identity_dir / f"{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        identity_views.append(
            {
                "name": name,
                "file": str(path.relative_to(output_dir)),
                "sha256": checksum(path),
                "bytes": path.stat().st_size,
            }
        )
    camera.matrix_world = original_matrix
    camera.data.ortho_scale = original_ortho_scale

    frames: list[dict[str, object]] = []
    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        path = idle_dir / f"{frame - scene.frame_start:02d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        frames.append(
            {
                "index": frame - scene.frame_start,
                "scene_frame": frame,
                "file": str(path.relative_to(output_dir)),
                "sha256": checksum(path),
                "bytes": path.stat().st_size,
            }
        )

    source_path = Path(bpy.data.filepath).resolve()
    repository_root = Path(__file__).resolve().parents[2]
    try:
        source_display = str(source_path.relative_to(repository_root))
    except ValueError:
        source_display = source_path.name
    manifest = {
        "schema_version": 1,
        "asset": "leo-the-dev",
        "status": "canonical-model-candidate-not-runtime-approved",
        "runtime_replacement": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": {
            "blender": bpy.app.version_string,
            "platform": platform.platform(),
            "source": source_display,
            "source_sha256": checksum(source_path),
            "script": "tools/blender/render_leo_idle.py",
        },
        "render": {
            "engine": scene.render.engine,
            "transparent": scene.render.film_transparent,
            "width": scene.render.resolution_x,
            "height": scene.render.resolution_y,
            "resolution_percentage": scene.render.resolution_percentage,
            "samples": args.samples,
            "color_mode": scene.render.image_settings.color_mode,
            "color_depth": scene.render.image_settings.color_depth,
        },
        "animation": {
            "name": "idle",
            "fps": scene.render.fps,
            "frame_duration_ms": round(1000 / scene.render.fps),
            "loop": True,
            "frames": frames,
        },
        "neutral": {
            "file": neutral_path.name,
            "sha256": checksum(neutral_path),
            "bytes": neutral_path.stat().st_size,
        },
        "identity_views": identity_views,
        "scene_validation": scene_validation,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"LEO_RENDER_DIR={output_dir}")
    print(f"LEO_MANIFEST={manifest_path}")


if __name__ == "__main__":
    main()
