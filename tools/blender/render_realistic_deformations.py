"""Render neutral and posed deformation checks for realistic Leo's test rig."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Quaternion, Vector

BODY_NAME = "Leo_Realistic_Body"
RIG_NAME = "RIG_Leo_Realistic"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=64)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def look_at(object_: bpy.types.Object, target: Vector) -> None:
    direction = target - object_.location
    object_.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def object_bounds(object_: bpy.types.Object) -> tuple[Vector, Vector]:
    corners = [object_.matrix_world @ Vector(corner) for corner in object_.bound_box]
    minimum = Vector(tuple(min(corner[axis] for corner in corners) for axis in range(3)))
    maximum = Vector(tuple(max(corner[axis] for corner in corners) for axis in range(3)))
    return minimum, maximum


def configure_scene(scene: bpy.types.Scene, samples: int) -> None:
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = True
    scene.render.resolution_x = 768
    scene.render.resolution_y = 832
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.use_stamp = False
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = samples
    with contextlib.suppress(TypeError):
        scene.view_settings.look = "AgX - Medium High Contrast"
    if scene.world and scene.world.use_nodes and scene.world.node_tree:
        background = scene.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs["Strength"].default_value = 0.16


def add_lights(target: Vector, scale: float) -> None:
    specs = (
        ("Key", (-0.65, -0.78, 1.00), 520.0, 0.60, (1.0, 0.96, 0.92)),
        ("Fill", (0.62, -0.43, 0.73), 260.0, 0.54, (0.88, 0.92, 1.0)),
        ("Rim", (0.24, 0.57, 0.92), 340.0, 0.48, (1.0, 0.88, 0.74)),
    )
    for name, direction, energy, size_ratio, color in specs:
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = scale * size_ratio
        data.color = color
        object_ = bpy.data.objects.new(name, data)
        object_.location = tuple(target[index] + scale * direction[index] for index in range(3))
        bpy.context.collection.objects.link(object_)
        look_at(object_, target)


def reset_pose(rig: bpy.types.Object) -> None:
    for pose_bone in rig.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = Quaternion()
        pose_bone.location = (0.0, 0.0, 0.0)
        pose_bone.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def rotate_about_armature_axis(
    rig: bpy.types.Object,
    bone_name: str,
    axis: tuple[float, float, float],
    degrees: float,
) -> None:
    pose_bone = rig.pose.bones[bone_name]
    axis_local = pose_bone.bone.matrix_local.to_3x3().inverted() @ Vector(axis)
    pose_bone.rotation_mode = "QUATERNION"
    pose_bone.rotation_quaternion = Quaternion(axis_local.normalized(), math.radians(degrees))


def apply_pose(rig: bpy.types.Object, rotations: list[tuple[str, str, float]]) -> None:
    reset_pose(rig)
    axes = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
    for bone_name, axis_name, degrees in rotations:
        rotate_about_armature_axis(rig, bone_name, axes[axis_name], degrees)
    bpy.context.view_layer.update()


def main() -> None:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    body = bpy.data.objects.get(BODY_NAME)
    rig = bpy.data.objects.get(RIG_NAME)
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Expected mesh object {BODY_NAME!r}")
    if rig is None or rig.type != "ARMATURE":
        raise RuntimeError(f"Expected armature object {RIG_NAME!r}")

    scene = bpy.context.scene
    configure_scene(scene, args.samples)
    reset_pose(rig)
    minimum, maximum = object_bounds(body)
    dimensions = maximum - minimum
    target = Vector(((minimum.x + maximum.x) / 2, 0.0, minimum.z + dimensions.z * 0.52))
    scale = max(dimensions) * 1.18

    camera_data = bpy.data.cameras.new("Deformation QA Camera")
    camera = bpy.data.objects.new("Deformation QA Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = scale
    scene.camera = camera
    add_lights(target, scale)

    poses: list[tuple[str, list[tuple[str, str, float]]]] = [
        ("neutral", []),
        ("head-yaw", [("neck", "z", 7.0), ("head", "z", 18.0)]),
        ("head-pitch", [("neck", "y", -6.0), ("head", "y", -14.0)]),
        (
            "foreleg-lift",
            [
                ("foreleg_upper.R", "y", -24.0),
                ("foreleg_lower.R", "y", 34.0),
                ("front_paw.R", "y", -12.0),
            ],
        ),
        (
            "hind-step",
            [
                ("hind_thigh.R", "y", 20.0),
                ("hind_shin.R", "y", -32.0),
                ("hind_paw.R", "y", 16.0),
            ],
        ),
        (
            "tail-curl",
            [
                ("tail.01", "y", -8.0),
                ("tail.02", "y", -13.0),
                ("tail.03", "y", -17.0),
                ("tail.04", "y", -20.0),
            ],
        ),
    ]
    views = (("side", 0.0), ("front", 90.0))
    frames: list[dict[str, Any]] = []
    for pose_index, (pose_name, rotations) in enumerate(poses):
        apply_pose(rig, rotations)
        for view_name, yaw in views:
            angle = math.radians(yaw)
            radius = scale * 1.35
            camera.location = (
                target.x + radius * math.sin(angle),
                target.y - radius * math.cos(angle),
                target.z + scale * 0.20,
            )
            look_at(camera, target)
            path = output_dir / f"pose-{pose_index:02d}-{pose_name}-{view_name}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            frames.append(
                {
                    "pose_index": pose_index,
                    "pose": pose_name,
                    "view": view_name,
                    "yaw": yaw,
                    "file": path.name,
                    "rotations": [
                        {"bone": bone, "axis": axis, "degrees": degrees}
                        for bone, axis, degrees in rotations
                    ],
                }
            )

    manifest = {
        "schema_version": 1,
        "source": source.name,
        "runtime_replacement": False,
        "body": BODY_NAME,
        "rig": RIG_NAME,
        "dimensions": [scene.render.resolution_x, scene.render.resolution_y],
        "views": [view_name for view_name, _yaw in views],
        "poses": [name for name, _rotations in poses],
        "frames": frames,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"LEO_REALISTIC_DEFORMATIONS={output_dir}")


if __name__ == "__main__":
    main()
