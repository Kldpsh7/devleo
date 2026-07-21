"""Render a neutral turntable for a reconstructed Leo mesh.

This is an isolated identity gate. It does not add the laptop, create a rig, or
replace any runtime sprites.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Matrix, Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--yaw-offset", type=float, default=0.0)
    parser.add_argument("--rotation-x", type=float, default=0.0)
    parser.add_argument("--rotation-y", type=float, default=0.0)
    parser.add_argument("--rotation-z", type=float, default=0.0)
    parser.add_argument("--smooth-factor", type=float, default=0.0)
    parser.add_argument("--smooth-iterations", type=int, default=0)
    parser.add_argument("--preserve-materials", action="store_true")
    parser.add_argument("--samples", type=int, default=64)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    corners = [
        object_.matrix_world @ Vector(corner) for object_ in objects for corner in object_.bound_box
    ]
    minimum = Vector(tuple(min(corner[axis] for corner in corners) for axis in range(3)))
    maximum = Vector(tuple(max(corner[axis] for corner in corners) for axis in range(3)))
    return minimum, maximum


def normalize(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    minimum, maximum = world_bounds(objects)
    dimensions = maximum - minimum
    scale = 3.75 / max(dimensions)
    scale_matrix = Matrix.Scale(scale, 4)
    for object_ in objects:
        # Scale the complete world transform so multi-object candidates keep
        # their facial details attached. Scaling only object.scale leaves each
        # object's origin in place and pulls eyes/muzzle parts off the body.
        object_.matrix_world = scale_matrix @ object_.matrix_world
    bpy.context.view_layer.update()
    minimum, maximum = world_bounds(objects)
    center = (minimum + maximum) / 2
    offset = Vector((-center.x, -center.y, -minimum.z))
    for object_ in objects:
        object_.location += offset
    bpy.context.view_layer.update()
    return world_bounds(objects)


def look_at(object_: bpy.types.Object, target: Vector) -> None:
    direction = target - object_.location
    object_.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_preview_material(object_: bpy.types.Object) -> None:
    mesh = object_.data
    material = bpy.data.materials.new(f"{object_.name} reconstructed color")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    principled = nodes.get("Principled BSDF")
    if principled is None:
        raise RuntimeError("Principled BSDF missing")
    if hasattr(mesh, "color_attributes") and mesh.color_attributes:
        color_attribute = mesh.color_attributes.active_color or mesh.color_attributes[0]
        color_node = nodes.new("ShaderNodeVertexColor")
        color_node.layer_name = color_attribute.name
        saturation = nodes.new("ShaderNodeHueSaturation")
        saturation.inputs["Saturation"].default_value = 1.32
        saturation.inputs["Value"].default_value = 0.78
        links.new(color_node.outputs["Color"], saturation.inputs["Color"])
        links.new(saturation.outputs["Color"], principled.inputs["Base Color"])
    else:
        principled.inputs["Base Color"].default_value = (0.62, 0.25, 0.055, 1.0)
    principled.inputs["Roughness"].default_value = 0.76
    object_.data.materials.clear()
    object_.data.materials.append(material)


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
    if hasattr(scene.view_settings, "look"):
        with contextlib.suppress(TypeError):
            scene.view_settings.look = "AgX - Medium High Contrast"
    if scene.world and scene.world.use_nodes and scene.world.node_tree:
        background = scene.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs["Strength"].default_value = 0.16


def add_lights(target: Vector) -> None:
    specs = (
        ("Key", (-4.8, -5.8, 7.4), 520.0, 4.5, (1.0, 0.96, 0.92)),
        ("Fill", (4.5, -3.2, 5.4), 260.0, 4.0, (0.88, 0.92, 1.0)),
        ("Rim", (1.8, 4.2, 6.8), 340.0, 3.5, (1.0, 0.88, 0.74)),
    )
    for name, location, energy, size, color in specs:
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = color
        object_ = bpy.data.objects.new(name, data)
        object_.location = location
        bpy.context.collection.objects.link(object_)
        look_at(object_, target)


def main() -> None:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(source))
    else:
        clear_scene()
        bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [object_ for object_ in bpy.context.scene.objects if object_.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh objects imported from {source}")
    rotation = (
        Matrix.Rotation(math.radians(args.rotation_z), 4, "Z")
        @ Matrix.Rotation(math.radians(args.rotation_y), 4, "Y")
        @ Matrix.Rotation(math.radians(args.rotation_x), 4, "X")
    )
    for mesh in meshes:
        mesh.matrix_world = rotation @ mesh.matrix_world
        if args.smooth_iterations > 0 and args.smooth_factor > 0:
            modifier = mesh.modifiers.new("Reconstruction cleanup", "SMOOTH")
            modifier.factor = args.smooth_factor
            modifier.iterations = args.smooth_iterations
            bpy.context.view_layer.objects.active = mesh
            mesh.select_set(True)
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            mesh.select_set(False)
        for polygon in mesh.data.polygons:
            polygon.use_smooth = True
        if not args.preserve_materials:
            add_preview_material(mesh)
    bpy.context.view_layer.update()
    minimum, maximum = normalize(meshes)

    scene = bpy.context.scene
    configure_scene(scene, args.samples)
    target = Vector((0.0, 0.0, (minimum.z + maximum.z) * 0.52))
    camera_data = bpy.data.cameras.new("Reconstruction Camera")
    camera = bpy.data.objects.new("Reconstruction Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 4.65
    scene.camera = camera
    add_lights(target)

    views: list[dict[str, Any]] = []
    for index, yaw in enumerate(range(0, 360, 45)):
        angle = math.radians(yaw + args.yaw_offset)
        camera.location = (7.4 * math.sin(angle), -7.4 * math.cos(angle), 3.7)
        look_at(camera, target)
        path = output_dir / f"view-{index:02d}-{yaw:03d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        views.append({"index": index, "yaw": yaw, "file": path.name})

    manifest = {
        "schema_version": 1,
        "source": source.name,
        "runtime_replacement": False,
        "source_rotation_degrees": [
            args.rotation_x,
            args.rotation_y,
            args.rotation_z,
        ],
        "cleanup": {
            "smooth_factor": args.smooth_factor,
            "smooth_iterations": args.smooth_iterations,
        },
        "preserve_materials": args.preserve_materials,
        "mesh_objects": [object_.name for object_ in meshes],
        "bounds": {
            "minimum": [round(value, 6) for value in minimum],
            "maximum": [round(value, 6) for value in maximum],
        },
        "views": views,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"LEO_RECONSTRUCTION_PREVIEW={output_dir}")


if __name__ == "__main__":
    main()
