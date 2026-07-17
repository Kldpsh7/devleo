"""Build Leo's canonical Blender source scene without external add-ons.

Run this file through Blender, not the system Python:

    blender --background --factory-startup --python tools/blender/build_leo_scene.py -- \
      --output assets/source-3d/leo.blend

The first scene is a reviewable 3D prototype. It deliberately stays separate from
the approved runtime sprites until its visual milestone is accepted.
"""

from __future__ import annotations

import argparse
import contextlib
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

PIPELINE_VERSION = 1
FRAME_START = 1
FRAME_END = 12
LOOP_FRAME = FRAME_END + 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def rgba(hex_color: str) -> tuple[float, float, float, float]:
    value = hex_color.removeprefix("#")
    return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)) + (1.0,)


def set_input(node: Any, name: str, value: Any) -> None:
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def material(
    name: str,
    color: str,
    *,
    roughness: float,
    metallic: float = 0.0,
    coat: float = 0.0,
    textured: bool = False,
) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = rgba(color)
    nodes = result.node_tree.nodes
    links = result.node_tree.links
    principled = nodes.get("Principled BSDF")
    if principled is None:
        raise RuntimeError("Blender did not create a Principled BSDF node")
    set_input(principled, "Base Color", rgba(color))
    set_input(principled, "Roughness", roughness)
    set_input(principled, "Metallic", metallic)
    set_input(principled, "Coat Weight", coat)

    if textured:
        coordinates = nodes.new("ShaderNodeTexCoord")
        noise = nodes.new("ShaderNodeTexNoise")
        ramp = nodes.new("ShaderNodeValToRGB")
        bump = nodes.new("ShaderNodeBump")
        noise.noise_dimensions = "3D"
        set_input(noise, "Scale", 11.0)
        set_input(noise, "Detail", 5.0)
        set_input(noise, "Roughness", 0.72)
        set_input(noise, "Distortion", 0.12)
        base = rgba(color)
        ramp.color_ramp.elements[0].position = 0.22
        ramp.color_ramp.elements[0].color = tuple(channel * 0.68 for channel in base[:3]) + (1.0,)
        ramp.color_ramp.elements[1].position = 0.82
        ramp.color_ramp.elements[1].color = tuple(
            min(1.0, channel * 1.15 + 0.03) for channel in base[:3]
        ) + (1.0,)
        set_input(bump, "Strength", 0.16)
        set_input(bump, "Distance", 0.055)
        links.new(coordinates.outputs["Generated"], noise.inputs["Vector"])
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    return result


def hair_material(name: str, color: str) -> bpy.types.Material:
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    nodes = result.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    hair = nodes.new("ShaderNodeBsdfHairPrincipled")
    hair.parametrization = "COLOR"
    set_input(hair, "Color", rgba(color))
    set_input(hair, "Roughness", 0.34)
    set_input(hair, "Radial Roughness", 0.42)
    set_input(hair, "Coat", 0.12)
    set_input(hair, "IOR", 1.48)
    set_input(hair, "Random Color", 0.08)
    set_input(hair, "Random Roughness", 0.12)
    result.node_tree.links.new(hair.outputs["BSDF"], output.inputs["Surface"])
    return result


def add_fur_system(
    object_: bpy.types.Object,
    fur_material: bpy.types.Material,
    *,
    count: int,
    length: float,
    seed: int,
) -> None:
    if fur_material.name not in object_.data.materials:
        object_.data.materials.append(fur_material)
    bpy.ops.object.select_all(action="DESELECT")
    object_.select_set(True)
    bpy.context.view_layer.objects.active = object_
    bpy.ops.object.particle_system_add()
    system = object_.particle_systems[-1]
    system.name = f"Fur_{object_.name}"
    system.seed = seed
    settings = system.settings
    settings.name = f"FurSettings_{object_.name}"
    settings.type = "HAIR"
    settings.count = count
    settings.hair_length = length
    settings.hair_step = 3
    settings.material_slot = fur_material.name
    settings.display_percentage = 12
    settings.use_hair_bspline = True
    settings.root_radius = 0.006
    settings.tip_radius = 0.0012
    settings.child_percent = 1
    settings.rendered_child_count = 8
    settings.clump_factor = 0.10
    settings.roughness_1 = 0.003
    settings.roughness_2 = 0.002
    settings.roughness_endpoint = 0.003
    if hasattr(settings, "child_type"):
        settings.child_type = "INTERPOLATED"
    if hasattr(settings, "render_type"):
        settings.render_type = "PATH"
    settings.effector_weights.gravity = 0.0


def apply_smooth(object_: bpy.types.Object) -> None:
    if object_.type != "MESH":
        return
    for polygon in object_.data.polygons:
        polygon.use_smooth = True


def add_ellipsoid(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    material_: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    segments: int = 48,
    rings: int = 32,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        location=location,
        rotation=rotation,
    )
    object_ = bpy.context.object
    object_.name = name
    object_.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    apply_smooth(object_)
    object_.data.materials.append(material_)
    return object_


def add_rounded_cube(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    material_: bpy.types.Material,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    bevel: float = 0.08,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location, rotation=rotation)
    object_ = bpy.context.object
    object_.name = name
    object_.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    modifier = object_.modifiers.new(name="Soft industrial edges", type="BEVEL")
    modifier.width = bevel
    modifier.segments = 5
    object_.data.materials.append(material_)
    return object_


def add_curve(
    name: str,
    points: list[tuple[float, float, float]],
    material_: bpy.types.Material,
    *,
    bevel_depth: float,
    taper: float = 1.0,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name=name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_resolution = 5
    curve.bevel_depth = bevel_depth
    curve.resolution_u = 24
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coordinate in zip(spline.bezier_points, points, strict=True):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
        point.radius = taper
    object_ = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(object_)
    curve.materials.append(material_)
    return object_


def add_empty(name: str, location: tuple[float, float, float]) -> bpy.types.Object:
    object_ = bpy.data.objects.new(name, None)
    object_.location = location
    object_.empty_display_type = "PLAIN_AXES"
    object_.empty_display_size = 0.18
    bpy.context.collection.objects.link(object_)
    return object_


def parent_keep_transform(child: bpy.types.Object, parent: bpy.types.Object) -> None:
    transform = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = transform


def keyframe(
    object_: bpy.types.Object,
    data_path: str,
    frame: int,
    value: tuple[float, float, float],
) -> None:
    setattr(object_, data_path, value)
    object_.keyframe_insert(data_path=data_path, frame=frame)


def look_at(object_: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - object_.location
    object_.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_production_rig() -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0.0, 0.0, 0.0))
    rig = bpy.context.object
    rig.name = "RIG_Leo"
    rig.data.name = "RIGDATA_Leo"
    for existing in list(rig.data.edit_bones):
        rig.data.edit_bones.remove(existing)

    bones: dict[str, bpy.types.EditBone] = {}

    def bone(
        name: str,
        head: tuple[float, float, float],
        tail: tuple[float, float, float],
        parent: str | None = None,
    ) -> bpy.types.EditBone:
        result = rig.data.edit_bones.new(name)
        result.head = head
        result.tail = tail
        if parent is not None:
            result.parent = bones[parent]
        bones[name] = result
        return result

    bone("root", (0.0, 0.1, 0.08), (0.0, 0.1, 0.52))
    bone("pelvis", (0.0, 0.1, 0.52), (0.0, 0.08, 1.28), "root")
    bone("spine", (0.0, 0.08, 1.28), (0.0, -0.03, 2.48), "pelvis")
    bone("neck", (0.0, -0.03, 2.48), (0.0, -0.10, 3.10), "spine")
    bone("head", (0.0, -0.10, 3.10), (0.0, -0.12, 4.25), "neck")
    for side, sign in (("L", -1.0), ("R", 1.0)):
        bone(
            f"foreleg_upper.{side}",
            (0.42 * sign, -0.18, 2.10),
            (0.48 * sign, -0.48, 1.27),
            "spine",
        )
        bone(
            f"foreleg_lower.{side}",
            (0.48 * sign, -0.48, 1.27),
            (0.50 * sign, -0.72, 0.52),
            f"foreleg_upper.{side}",
        )
        bone(
            f"front_paw.{side}",
            (0.50 * sign, -0.72, 0.52),
            (0.52 * sign, -1.05, 0.25),
            f"foreleg_lower.{side}",
        )
        bone(
            f"hind_thigh.{side}",
            (0.42 * sign, 0.12, 1.25),
            (0.72 * sign, 0.13, 0.78),
            "pelvis",
        )
        bone(
            f"hind_paw.{side}",
            (0.72 * sign, 0.13, 0.78),
            (0.68 * sign, -0.72, 0.31),
            f"hind_thigh.{side}",
        )
    bone("tail.01", (0.58, 0.28, 1.18), (1.05, 0.38, 1.05), "pelvis")
    bone("tail.02", (1.05, 0.38, 1.05), (1.42, 0.02, 0.79), "tail.01")
    bone("tail.03", (1.42, 0.02, 0.79), (1.16, -0.70, 0.72), "tail.02")
    laptop = bone("prop_laptop", (0.0, -0.55, 0.30), (0.0, -1.58, 0.30), "root")
    laptop.use_deform = False

    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    rig.data.display_type = "OCTAHEDRAL"
    rig.display_type = "WIRE"
    rig.hide_render = True
    rig["rig_version"] = 1
    rig["rig_contract"] = "root/pelvis/spine/head, quadruped limbs, tail chain, laptop prop"
    return rig


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


def build_scene() -> bpy.types.Scene:
    clear_scene()
    scene = bpy.context.scene
    scene.name = "Leo Idle Prototype"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.film_transparent = True
    scene.render.resolution_x = 1152
    scene.render.resolution_y = 1248
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 18
    disable_render_stamps(scene)
    scene.render.fps = 6
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.world.color = (0.025, 0.025, 0.025)
    with contextlib.suppress(TypeError):
        scene.view_settings.look = "AgX - Medium High Contrast"
    scene["leo_pipeline_version"] = PIPELINE_VERSION
    scene["leo_asset_status"] = "canonical-model-candidate-not-runtime-approved"
    scene["leo_identity"] = "young quadrupedal lion cub with a silver laptop"

    fur = material("Leo golden coat", "C9792E", roughness=0.62, textured=True)
    pale_fur = material("Leo muzzle and chest", "E8B96D", roughness=0.68, textured=True)
    dark_fur = material("Leo markings and tail tuft", "5B2E17", roughness=0.72, textured=True)
    fur_fibers = hair_material("Leo golden fur fibers", "B96825")
    pale_fibers = hair_material("Leo pale fur fibers", "DFA85E")
    inner_ear = material("Leo inner ear", "A95745", roughness=0.78)
    eye_rim = material("Natural dark eye rim", "2B1B14", roughness=0.34, coat=0.16)
    iris = material("Amber iris", "D89524", roughness=0.24, coat=0.35)
    pupil = material("Eye pupil", "17110D", roughness=0.22, coat=0.25)
    highlight = material("Eye highlight", "FFFFFF", roughness=0.08, coat=0.6)
    nose = material("Nose", "3A201C", roughness=0.48, coat=0.12)
    laptop_silver = material("Laptop silver", "AEB4BC", roughness=0.25, metallic=0.82)
    laptop_edge = material("Laptop edge", "343A42", roughness=0.34, metallic=0.55)
    laptop_dark = material("Laptop screen and keyboard", "11161D", roughness=0.30, metallic=0.18)

    body_ctrl = add_empty("CTRL_Body_Breath", (0.0, 0.0, 1.7))
    head_ctrl = add_empty("CTRL_Head_Glance", (0.0, -0.10, 3.68))
    tail_ctrl = add_empty("CTRL_Tail_Flick", (0.72, 0.38, 1.22))
    left_blink = add_empty("CTRL_Blink_L", (-0.34, -0.91, 3.84))
    right_blink = add_empty("CTRL_Blink_R", (0.34, -0.91, 3.84))
    left_gaze = add_empty("CTRL_Eye_Gaze_L", (-0.25, -0.995, 3.895))
    right_gaze = add_empty("CTRL_Eye_Gaze_R", (0.43, -0.995, 3.895))
    left_ear_ctrl = add_empty("CTRL_Ear_L", (-0.70, -0.03, 4.23))
    right_ear_ctrl = add_empty("CTRL_Ear_R", (0.70, -0.03, 4.23))
    laptop_lid_ctrl = add_empty("CTRL_Laptop_Lid", (0.0, -2.13, 0.265))

    body_parts = [
        add_ellipsoid("Torso", (0.0, 0.04, 2.03), (0.83, 0.69, 1.20), fur),
        add_ellipsoid("Chest", (0.0, -0.58, 1.73), (0.56, 0.27, 0.88), pale_fur),
        add_ellipsoid("Haunch_L", (-0.71, 0.18, 1.04), (0.67, 0.69, 0.72), fur),
        add_ellipsoid("Haunch_R", (0.71, 0.18, 1.04), (0.67, 0.69, 0.72), fur),
        add_ellipsoid("Hind_Paw_L", (-0.65, -0.65, 0.39), (0.52, 0.61, 0.27), fur),
        add_ellipsoid("Hind_Paw_R", (0.65, -0.65, 0.39), (0.52, 0.61, 0.27), fur),
        add_ellipsoid(
            "Foreleg_L_Upper",
            (-0.48, -0.49, 1.43),
            (0.27, 0.31, 0.79),
            fur,
            rotation=(math.radians(-5), 0.0, math.radians(-2)),
        ),
        add_ellipsoid(
            "Foreleg_R_Upper",
            (0.48, -0.49, 1.43),
            (0.27, 0.31, 0.79),
            fur,
            rotation=(math.radians(-5), 0.0, math.radians(2)),
        ),
        add_ellipsoid("Foreleg_L_Lower", (-0.50, -0.69, 0.78), (0.29, 0.34, 0.58), fur),
        add_ellipsoid("Foreleg_R_Lower", (0.50, -0.69, 0.78), (0.29, 0.34, 0.58), fur),
        add_ellipsoid("Front_Paw_L", (-0.51, -0.89, 0.28), (0.38, 0.49, 0.23), fur),
        add_ellipsoid("Front_Paw_R", (0.51, -0.89, 0.28), (0.38, 0.49, 0.23), fur),
    ]
    for part in body_parts:
        parent_keep_transform(part, body_ctrl)

    head_parts = [
        add_ellipsoid("Head", (0.0, -0.12, 3.66), (1.00, 0.80, 0.93), fur),
        add_ellipsoid("Muzzle_L", (-0.31, -0.84, 3.42), (0.42, 0.31, 0.35), pale_fur),
        add_ellipsoid("Muzzle_R", (0.31, -0.84, 3.42), (0.42, 0.31, 0.35), pale_fur),
        add_ellipsoid("Chin", (0.0, -0.78, 3.23), (0.42, 0.25, 0.23), pale_fur),
        add_ellipsoid("Nose", (0.0, -1.16, 3.54), (0.20, 0.12, 0.15), nose),
    ]
    for part in head_parts:
        parent_keep_transform(part, head_ctrl)

    mouth = add_curve(
        "Mouth",
        [(-0.18, -1.105, 3.34), (0.0, -1.14, 3.29), (0.18, -1.105, 3.34)],
        nose,
        bevel_depth=0.018,
    )
    parent_keep_transform(mouth, head_ctrl)

    for side, x in (("L", -0.70), ("R", 0.70)):
        control = left_ear_ctrl if side == "L" else right_ear_ctrl
        outer = add_ellipsoid(f"Ear_{side}", (x, -0.02, 4.24), (0.36, 0.20, 0.42), fur)
        inner = add_ellipsoid(
            f"Inner_Ear_{side}", (x, -0.205, 4.24), (0.23, 0.075, 0.28), inner_ear
        )
        parent_keep_transform(outer, control)
        parent_keep_transform(inner, control)
        parent_keep_transform(control, head_ctrl)

    for side, x, blink_ctrl, gaze_ctrl in (
        ("L", -0.34, left_blink, left_gaze),
        ("R", 0.34, right_blink, right_gaze),
    ):
        globe = add_ellipsoid(f"Eye_{side}", (x, -0.88, 3.84), (0.205, 0.125, 0.250), eye_rim)
        iris_object = add_ellipsoid(
            f"Iris_{side}",
            (x + 0.05, -1.04, 3.87),
            (0.155, 0.040, 0.195),
            iris,
            segments=40,
            rings=24,
        )
        pupil_object = add_ellipsoid(
            f"Pupil_{side}",
            (x + 0.065, -1.08, 3.875),
            (0.050, 0.020, 0.112),
            pupil,
            segments=32,
            rings=20,
        )
        glint = add_ellipsoid(
            f"Eye_Glint_{side}",
            (x + 0.035, -1.098, 3.94),
            (0.025, 0.010, 0.032),
            highlight,
            segments=24,
            rings=16,
        )
        parent_keep_transform(globe, blink_ctrl)
        for part in (iris_object, pupil_object, glint):
            parent_keep_transform(part, gaze_ctrl)
        parent_keep_transform(gaze_ctrl, blink_ctrl)
        parent_keep_transform(blink_ctrl, head_ctrl)
    gaze_controls = (
        (left_gaze, tuple(left_gaze.location)),
        (right_gaze, tuple(right_gaze.location)),
    )

    stripe_points = [
        (-0.38, 4.18, -8),
        (-0.19, 4.28, -3),
        (0.0, 4.32, 0),
        (0.19, 4.28, 3),
        (0.38, 4.18, 8),
    ]
    for index, (x, z, angle) in enumerate(stripe_points):
        stripe = add_ellipsoid(
            f"Forehead_Stripe_{index}",
            (x, -0.900, z),
            (0.045, 0.014, 0.13),
            dark_fur,
            rotation=(0.0, math.radians(angle), 0.0),
            segments=28,
            rings=16,
        )
        parent_keep_transform(stripe, head_ctrl)

    whisker_specs = [
        ((-0.28, -1.09, 3.46), (-0.73, -1.17, 3.50), (-1.08, -1.10, 3.56)),
        ((-0.29, -1.09, 3.40), (-0.75, -1.18, 3.36), (-1.10, -1.09, 3.34)),
        ((0.28, -1.09, 3.46), (0.73, -1.17, 3.50), (1.08, -1.10, 3.56)),
        ((0.29, -1.09, 3.40), (0.75, -1.18, 3.36), (1.10, -1.09, 3.34)),
    ]
    for index, points in enumerate(whisker_specs):
        whisker = add_curve(f"Whisker_{index}", list(points), pale_fur, bevel_depth=0.009)
        parent_keep_transform(whisker, head_ctrl)

    for side, sign in (("L", -1.0), ("R", 1.0)):
        for index, (x_offset, z_offset) in enumerate(((0.0, 0.0), (0.08, 0.045), (0.09, -0.055))):
            spot = add_ellipsoid(
                f"Whisker_Spot_{side}_{index}",
                (sign * (0.34 + x_offset), -1.145, 3.43 + z_offset),
                (0.015, 0.009, 0.015),
                nose,
                segments=16,
                rings=10,
            )
            parent_keep_transform(spot, head_ctrl)

    tail = add_curve(
        "Tail",
        [
            (0.69, 0.36, 1.24),
            (1.18, 0.45, 1.12),
            (1.45, 0.12, 0.85),
            (1.39, -0.35, 0.68),
            (1.15, -0.68, 0.74),
        ],
        fur,
        bevel_depth=0.13,
    )
    tail_tuft = add_ellipsoid(
        "Tail_Tuft",
        (1.12, -0.72, 0.74),
        (0.22, 0.25, 0.30),
        dark_fur,
        rotation=(math.radians(12), 0.0, math.radians(-18)),
    )
    parent_keep_transform(tail, tail_ctrl)
    parent_keep_transform(tail_tuft, tail_ctrl)
    parent_keep_transform(tail_ctrl, body_ctrl)
    parent_keep_transform(head_ctrl, body_ctrl)

    laptop_rim = add_rounded_cube(
        "Laptop_Dark_Rim", (0.0, -1.37, 0.160), (2.82, 1.68, 0.10), laptop_edge, bevel=0.08
    )
    add_rounded_cube(
        "Laptop_Base_Deck",
        (0.0, -1.37, 0.205),
        (2.72, 1.58, 0.075),
        laptop_silver,
        bevel=0.07,
    )
    add_rounded_cube(
        "Laptop_Keyboard_Well",
        (0.0, -1.16, 0.247),
        (2.18, 0.80, 0.018),
        laptop_dark,
        bevel=0.035,
    )
    add_rounded_cube(
        "Laptop_Trackpad",
        (0.0, -1.78, 0.247),
        (0.92, 0.44, 0.016),
        laptop_edge,
        bevel=0.045,
    )
    laptop_lid_rim = add_rounded_cube(
        "Laptop_Lid_Rim",
        (0.0, -1.37, 0.250),
        (2.80, 1.66, 0.060),
        laptop_edge,
        bevel=0.08,
    )
    laptop_screen = add_rounded_cube(
        "Laptop_Screen",
        (0.0, -1.37, 0.224),
        (2.55, 1.40, 0.018),
        laptop_dark,
        bevel=0.055,
    )
    laptop_lid = add_rounded_cube(
        "Laptop_Closed_Lid",
        (0.0, -1.37, 0.292),
        (2.72, 1.58, 0.065),
        laptop_silver,
        bevel=0.075,
    )
    add_rounded_cube(
        "Laptop_Hinge", (0.0, -2.13, 0.315), (2.32, 0.11, 0.10), laptop_edge, bevel=0.04
    )
    paw_pad = add_ellipsoid(
        "Laptop_Paw_Emblem_Pad",
        (0.0, -1.43, 0.326),
        (0.18, 0.14, 0.025),
        laptop_edge,
        segments=32,
        rings=16,
    )
    paw_pad.rotation_euler.z = math.radians(8)
    paw_emblem_parts = [paw_pad]
    for index, (x, y, scale) in enumerate(
        ((-0.19, -1.26, 0.07), (-0.065, -1.19, 0.075), (0.07, -1.19, 0.075), (0.19, -1.27, 0.07))
    ):
        toe = add_ellipsoid(
            f"Laptop_Paw_Emblem_Toe_{index}",
            (x, y, 0.329),
            (scale, scale * 0.86, 0.022),
            laptop_edge,
            segments=24,
            rings=12,
        )
        paw_emblem_parts.append(toe)
    for part in (laptop_lid_rim, laptop_screen, laptop_lid, *paw_emblem_parts):
        parent_keep_transform(part, laptop_lid_ctrl)
    laptop_lid_ctrl["closed_degrees"] = 0.0
    laptop_lid_ctrl["waiting_degrees"] = 48.0
    laptop_lid_ctrl["working_degrees"] = 96.0
    laptop_rim["state"] = "closed"
    laptop_rim["design_rule"] = "broad exterior lid remains visible at minimum runtime scale"

    fur_specs = (
        ("Head", fur_fibers, 8200, 0.028),
        ("Torso", fur_fibers, 6200, 0.032),
        ("Chest", pale_fibers, 2400, 0.026),
        ("Haunch_L", fur_fibers, 3000, 0.030),
        ("Haunch_R", fur_fibers, 3000, 0.030),
        ("Muzzle_L", pale_fibers, 1000, 0.022),
        ("Muzzle_R", pale_fibers, 1000, 0.022),
        ("Chin", pale_fibers, 650, 0.020),
        ("Ear_L", fur_fibers, 900, 0.024),
        ("Ear_R", fur_fibers, 900, 0.024),
        ("Foreleg_L_Upper", fur_fibers, 1300, 0.026),
        ("Foreleg_R_Upper", fur_fibers, 1300, 0.026),
        ("Foreleg_L_Lower", fur_fibers, 1100, 0.025),
        ("Foreleg_R_Lower", fur_fibers, 1100, 0.025),
        ("Front_Paw_L", fur_fibers, 950, 0.023),
        ("Front_Paw_R", fur_fibers, 950, 0.023),
        ("Hind_Paw_L", fur_fibers, 1100, 0.025),
        ("Hind_Paw_R", fur_fibers, 1100, 0.025),
    )
    for seed, (name, fibers, count, length) in enumerate(fur_specs, start=110):
        add_fur_system(bpy.data.objects[name], fibers, count=count, length=length, seed=seed)

    rig = add_production_rig()
    scene["leo_rig_version"] = rig["rig_version"]

    camera_data = bpy.data.cameras.new("Leo Camera")
    camera = bpy.data.objects.new("Leo Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (4.55, -12.8, 6.25)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 5.55
    camera.data.lens = 56
    look_at(camera, (0.0, -0.42, 2.20))
    scene.camera = camera

    lights = [
        ("Key softbox", "AREA", (-4.5, -5.5, 8.0), 1050.0, 5.0, (1.0, 0.73, 0.50)),
        ("Fill softbox", "AREA", (5.0, -3.0, 5.4), 760.0, 4.0, (0.56, 0.72, 1.0)),
        ("Rim softbox", "AREA", (1.0, 4.0, 7.0), 920.0, 3.5, (1.0, 0.50, 0.24)),
    ]
    for name, type_, location, energy, size, color in lights:
        data = bpy.data.lights.new(name=name, type=type_)
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = color
        object_ = bpy.data.objects.new(name, data)
        object_.location = location
        bpy.context.collection.objects.link(object_)
        look_at(object_, (0.0, -0.25, 2.0))

    for frame, scale in (
        (1, (1.0, 1.0, 1.0)),
        (4, (1.006, 1.006, 1.016)),
        (7, (1.0, 1.0, 1.0)),
        (10, (0.997, 0.997, 0.990)),
        (LOOP_FRAME, (1.0, 1.0, 1.0)),
    ):
        keyframe(body_ctrl, "scale", frame, scale)

    for frame, rotation in (
        (1, (0.0, 0.0, 0.0)),
        (5, (math.radians(0.6), math.radians(-0.8), math.radians(-1.0))),
        (8, (math.radians(-0.4), math.radians(1.2), math.radians(2.8))),
        (11, (math.radians(0.2), math.radians(-0.4), math.radians(0.8))),
        (LOOP_FRAME, (0.0, 0.0, 0.0)),
    ):
        keyframe(head_ctrl, "rotation_euler", frame, rotation)

    for gaze_ctrl, base in gaze_controls:
        for frame, offset in (
            (1, (0.0, 0.0, 0.0)),
            (5, (0.0, 0.0, 0.0)),
            (7, (0.035, -0.002, 0.018)),
            (9, (0.012, -0.001, 0.008)),
            (LOOP_FRAME, (0.0, 0.0, 0.0)),
        ):
            keyframe(
                gaze_ctrl,
                "location",
                frame,
                tuple(base[index] + offset[index] for index in range(3)),
            )

    for blink_ctrl in (left_blink, right_blink):
        for frame, scale in (
            (1, (1.0, 1.0, 1.0)),
            (8, (1.0, 1.0, 1.0)),
            (9, (1.0, 1.0, 0.08)),
            (10, (1.0, 1.0, 1.0)),
            (LOOP_FRAME, (1.0, 1.0, 1.0)),
        ):
            keyframe(blink_ctrl, "scale", frame, scale)

    for frame, rotation in (
        (1, (0.0, 0.0, math.radians(-2.0))),
        (4, (0.0, 0.0, math.radians(4.0))),
        (7, (math.radians(1.5), 0.0, math.radians(-5.0))),
        (9, (math.radians(-2.0), 0.0, math.radians(7.0))),
        (11, (0.0, 0.0, math.radians(-2.0))),
        (LOOP_FRAME, (0.0, 0.0, math.radians(-2.0))),
    ):
        keyframe(tail_ctrl, "rotation_euler", frame, rotation)

    for control, sign in ((left_ear_ctrl, -1.0), (right_ear_ctrl, 1.0)):
        for frame, rotation in (
            (1, (0.0, 0.0, 0.0)),
            (6, (0.0, 0.0, 0.0)),
            (7, (math.radians(-2.4), 0.0, math.radians(sign * 3.8))),
            (8, (math.radians(1.2), 0.0, math.radians(sign * -1.8))),
            (9, (0.0, 0.0, 0.0)),
            (LOOP_FRAME, (0.0, 0.0, 0.0)),
        ):
            keyframe(control, "rotation_euler", frame, rotation)

    scene.frame_set(FRAME_START)
    return scene


def main() -> None:
    args = parse_args()
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    build_scene()
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    print(f"LEO_SCENE={output}")


if __name__ == "__main__":
    main()
