"""Refine Leo's project-owned realistic sculpt identity candidate.

Run this file through Blender, not the system Python:

    blender --background --factory-startup \
      --python tools/blender/refine_realistic_leo.py -- \
      --input /path/to/leo-sculpt.blend \
      --output assets/source-3d/leo-realistic.blend

The script deliberately stops at the identity gate. It does not add a rig,
laptop, animation, or copy renders into the runtime package.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path
from typing import Any

import bpy

PIPELINE_VERSION = 1
DETAIL_PREFIX = "IDENTITY_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--glb", type=Path)
    parser.add_argument("--textures-dir", type=Path)
    parser.add_argument("--smooth-factor", type=float, default=0.50)
    parser.add_argument("--smooth-iterations", type=int, default=5)
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def rgba(hex_color: str) -> tuple[float, float, float, float]:
    value = hex_color.removeprefix("#")
    return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)) + (1.0,)


def set_input(node: Any, name: str, value: Any) -> None:
    socket = node.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def solid_material(
    name: str,
    color: str,
    *,
    roughness: float,
    metallic: float = 0.0,
    coat: float = 0.0,
) -> bpy.types.Material:
    result = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = rgba(color)
    nodes = result.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    set_input(principled, "Base Color", rgba(color))
    set_input(principled, "Roughness", roughness)
    set_input(principled, "Metallic", metallic)
    set_input(principled, "Coat Weight", coat)
    result.node_tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return result


def coat_material(name: str, dark: str, mid: str, light: str) -> bpy.types.Material:
    """Create fine-scale coat variation without changing the sculpt silhouette."""
    result = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    result.use_nodes = True
    nodes = result.node_tree.nodes
    nodes.clear()
    links = result.node_tree.links

    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    coordinates = nodes.new("ShaderNodeTexCoord")
    broad_noise = nodes.new("ShaderNodeTexNoise")
    fine_noise = nodes.new("ShaderNodeTexNoise")
    ramp = nodes.new("ShaderNodeValToRGB")
    bump = nodes.new("ShaderNodeBump")

    broad_noise.noise_dimensions = "3D"
    set_input(broad_noise, "Scale", 7.5)
    set_input(broad_noise, "Detail", 4.5)
    set_input(broad_noise, "Roughness", 0.68)
    set_input(broad_noise, "Distortion", 0.08)
    fine_noise.noise_dimensions = "3D"
    set_input(fine_noise, "Scale", 72.0)
    set_input(fine_noise, "Detail", 3.0)
    set_input(fine_noise, "Roughness", 0.54)

    ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
    for position, color in ((0.18, dark), (0.50, mid), (0.82, light)):
        element = (
            ramp.color_ramp.elements[0]
            if position == 0.18
            else ramp.color_ramp.elements.new(position)
        )
        element.position = position
        element.color = rgba(color)

    set_input(principled, "Roughness", 0.66)
    set_input(principled, "Sheen Weight", 0.10)
    set_input(bump, "Strength", 0.045)
    set_input(bump, "Distance", 0.018)
    links.new(coordinates.outputs["Generated"], broad_noise.inputs["Vector"])
    links.new(coordinates.outputs["Generated"], fine_noise.inputs["Vector"])
    links.new(broad_noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
    links.new(fine_noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return result


def remove_previous_identity_details() -> None:
    legacy_names = {
        "Eye_L",
        "Eye_R",
        "Iris_L",
        "Iris_R",
        "Pupil_L",
        "Pupil_R",
        "Muzzle_L",
        "Muzzle_R",
        "Nose",
        "Chin",
    }
    for object_ in list(bpy.context.scene.objects):
        if object_.name in legacy_names or object_.name.startswith(DETAIL_PREFIX):
            bpy.data.objects.remove(object_, do_unlink=True)


def smooth_body(body: bpy.types.Object, factor: float, iterations: int) -> None:
    if factor <= 0 or iterations <= 0:
        return
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    modifier = body.modifiers.new("Identity surface cleanup", "SMOOTH")
    modifier.factor = factor
    modifier.iterations = iterations
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    body.select_set(False)
    for polygon in body.data.polygons:
        polygon.use_smooth = True


def reshape_head(body: bpy.types.Object) -> None:
    """Gently broaden the cub skull and shorten only the front of the muzzle."""
    for vertex in body.data.vertices:
        coordinate = vertex.co
        head_weight = max(0.0, min(1.0, (coordinate.z - 2.05) / 0.65))
        head_weight *= max(0.0, min(1.0, (coordinate.x - 0.72) / 0.55))
        if head_weight == 0.0:
            continue
        coordinate.y *= 1.0 + 0.08 * head_weight
        if coordinate.x > 2.02:
            coordinate.x = 2.02 + (coordinate.x - 2.02) * (1.0 - 0.08 * head_weight)


def sculpt_eye_sockets(body: bpy.types.Object) -> None:
    """Recess two eye apertures into the retained head surface."""
    for sign in (1.0, -1.0):
        center_y = 0.270 * sign
        center_z = 2.625
        for vertex in body.data.vertices:
            coordinate = vertex.co
            if coordinate.x < 2.0:
                continue
            dy = (coordinate.y - center_y) / 0.19
            dz = (coordinate.z - center_z) / 0.155
            radius_squared = dy * dy + dz * dz
            if radius_squared >= 1.0:
                continue
            target_x = 2.205 + 0.095 * radius_squared
            coordinate.x = min(coordinate.x, target_x)
    body.data.update()


def add_ellipsoid(
    name: str,
    location: tuple[float, float, float],
    scale: tuple[float, float, float],
    material: bpy.types.Material,
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
    object_.name = f"{DETAIL_PREFIX}{name}"
    object_.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for polygon in object_.data.polygons:
        polygon.use_smooth = True
    object_.data.materials.append(material)
    return object_


def add_curve(
    name: str,
    points: list[tuple[float, float, float]],
    material: bpy.types.Material,
    *,
    bevel_depth: float,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name=f"{DETAIL_PREFIX}{name}", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_resolution = 4
    curve.bevel_depth = bevel_depth
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for point, coordinate in zip(spline.bezier_points, points, strict=True):
        point.co = coordinate
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    object_ = bpy.data.objects.new(curve.name, curve)
    bpy.context.collection.objects.link(object_)
    curve.materials.append(material)
    return object_


def apply_turnaround_projection(body: bpy.types.Object, textures_dir: Path) -> None:
    """Blend four approved turnaround views over the project-owned sculpt."""
    paths = {
        name: (
            textures_dir / f"{name}-projection.png"
            if (textures_dir / f"{name}-projection.png").exists()
            else textures_dir / f"{name}.png"
        )
        for name in ("front", "left", "rear", "right")
    }
    missing = [path for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing turnaround textures: {missing}")

    material = bpy.data.materials.get(
        "Leo project-owned turnaround projection"
    ) or bpy.data.materials.new("Leo project-owned turnaround projection")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    coordinates = nodes.new("ShaderNodeTexCoord")
    geometry = nodes.new("ShaderNodeNewGeometry")
    separate_coordinates = nodes.new("ShaderNodeSeparateXYZ")
    separate_normal = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coordinates.outputs["Generated"], separate_coordinates.inputs["Vector"])
    links.new(geometry.outputs["Normal"], separate_normal.inputs["Vector"])

    def invert(value: bpy.types.NodeSocket) -> bpy.types.NodeSocket:
        node = nodes.new("ShaderNodeMath")
        node.operation = "SUBTRACT"
        node.inputs[0].default_value = 1.0
        links.new(value, node.inputs[1])
        return node.outputs[0]

    def positive(value: bpy.types.NodeSocket, *, negate: bool = False) -> bpy.types.NodeSocket:
        source = value
        if negate:
            multiply = nodes.new("ShaderNodeMath")
            multiply.operation = "MULTIPLY"
            multiply.inputs[1].default_value = -1.0
            links.new(value, multiply.inputs[0])
            source = multiply.outputs[0]
        maximum = nodes.new("ShaderNodeMath")
        maximum.operation = "MAXIMUM"
        maximum.inputs[1].default_value = 0.0
        links.new(source, maximum.inputs[0])
        power = nodes.new("ShaderNodeMath")
        power.operation = "POWER"
        power.inputs[1].default_value = 3.0
        links.new(maximum.outputs[0], power.inputs[0])
        return power.outputs[0]

    mappings = {
        "front": (separate_coordinates.outputs["Y"], separate_coordinates.outputs["Z"]),
        "rear": (invert(separate_coordinates.outputs["Y"]), separate_coordinates.outputs["Z"]),
        "left": (invert(separate_coordinates.outputs["X"]), separate_coordinates.outputs["Z"]),
        "right": (separate_coordinates.outputs["X"], separate_coordinates.outputs["Z"]),
    }
    weights = {
        "front": positive(separate_normal.outputs["X"]),
        "rear": positive(separate_normal.outputs["X"], negate=True),
        "left": positive(separate_normal.outputs["Y"]),
        "right": positive(separate_normal.outputs["Y"], negate=True),
    }
    vertical_absolute = nodes.new("ShaderNodeMath")
    vertical_absolute.operation = "ABSOLUTE"
    links.new(separate_normal.outputs["Z"], vertical_absolute.inputs[0])
    vertical_power = nodes.new("ShaderNodeMath")
    vertical_power.operation = "POWER"
    vertical_power.inputs[1].default_value = 3.0
    links.new(vertical_absolute.outputs[0], vertical_power.inputs[0])
    weights["vertical"] = vertical_power.outputs[0]

    fallback = rgba("#B85F18")
    weighted_colors: list[bpy.types.NodeSocket] = []
    for name in ("front", "left", "rear", "right"):
        combine = nodes.new("ShaderNodeCombineXYZ")
        links.new(mappings[name][0], combine.inputs["X"])
        links.new(mappings[name][1], combine.inputs["Y"])
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = bpy.data.images.load(str(paths[name].resolve()), check_existing=True)
        texture.image.pack()
        texture.extension = "CLIP"
        texture.interpolation = "Linear"
        links.new(combine.outputs["Vector"], texture.inputs["Vector"])
        alpha_mix = nodes.new("ShaderNodeMixRGB")
        alpha_mix.blend_type = "MIX"
        alpha_mix.inputs[1].default_value = fallback
        links.new(texture.outputs["Alpha"], alpha_mix.inputs[0])
        links.new(texture.outputs["Color"], alpha_mix.inputs[2])
        multiply = nodes.new("ShaderNodeMixRGB")
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1.0
        links.new(alpha_mix.outputs["Color"], multiply.inputs[1])
        weight_vector = nodes.new("ShaderNodeCombineXYZ")
        for axis in ("X", "Y", "Z"):
            links.new(weights[name], weight_vector.inputs[axis])
        links.new(weight_vector.outputs["Vector"], multiply.inputs[2])
        weighted_colors.append(multiply.outputs["Color"])

    vertical_color = nodes.new("ShaderNodeMixRGB")
    vertical_color.blend_type = "MULTIPLY"
    vertical_color.inputs[0].default_value = 1.0
    dorsal_noise = nodes.new("ShaderNodeTexNoise")
    dorsal_noise.noise_dimensions = "3D"
    set_input(dorsal_noise, "Scale", 12.0)
    set_input(dorsal_noise, "Detail", 4.0)
    set_input(dorsal_noise, "Roughness", 0.68)
    dorsal_ramp = nodes.new("ShaderNodeValToRGB")
    dorsal_ramp.color_ramp.elements[0].position = 0.20
    dorsal_ramp.color_ramp.elements[0].color = rgba("#421706")
    dorsal_ramp.color_ramp.elements[1].position = 0.82
    dorsal_ramp.color_ramp.elements[1].color = rgba("#8C4716")
    links.new(coordinates.outputs["Generated"], dorsal_noise.inputs["Vector"])
    links.new(dorsal_noise.outputs["Fac"], dorsal_ramp.inputs["Fac"])
    links.new(dorsal_ramp.outputs["Color"], vertical_color.inputs[1])
    vertical_weight_vector = nodes.new("ShaderNodeCombineXYZ")
    for axis in ("X", "Y", "Z"):
        links.new(weights["vertical"], vertical_weight_vector.inputs[axis])
    links.new(vertical_weight_vector.outputs["Vector"], vertical_color.inputs[2])
    weighted_colors.append(vertical_color.outputs["Color"])

    color_sum = weighted_colors[0]
    for color in weighted_colors[1:]:
        add = nodes.new("ShaderNodeMixRGB")
        add.blend_type = "ADD"
        add.inputs[0].default_value = 1.0
        links.new(color_sum, add.inputs[1])
        links.new(color, add.inputs[2])
        color_sum = add.outputs["Color"]

    weight_sum = weights["front"]
    for name in ("left", "rear", "right", "vertical"):
        add = nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        links.new(weight_sum, add.inputs[0])
        links.new(weights[name], add.inputs[1])
        weight_sum = add.outputs[0]
    weight_vector = nodes.new("ShaderNodeCombineXYZ")
    for axis in ("X", "Y", "Z"):
        links.new(weight_sum, weight_vector.inputs[axis])
    divide = nodes.new("ShaderNodeVectorMath")
    divide.operation = "DIVIDE"
    links.new(color_sum, divide.inputs[0])
    links.new(weight_vector.outputs["Vector"], divide.inputs[1])

    set_input(principled, "Roughness", 0.68)
    set_input(principled, "Sheen Weight", 0.10)
    links.new(divide.outputs["Vector"], principled.inputs["Base Color"])
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    body.data.materials.clear()
    body.data.materials.append(material)
    for polygon in body.data.polygons:
        polygon.material_index = 0
    body["turnaround_projection"] = "front/left/rear/right project-owned reference blend"


def build_face() -> None:
    coat = coat_material("Leo refined golden coat", "#5F270C", "#A95013", "#D77E25")
    cream = coat_material("Leo refined cream fur", "#9A5925", "#D69A55", "#F0C982")
    dark = solid_material("Leo refined dark markings", "#2A1710", roughness=0.72)
    inner_ear = solid_material("Leo refined inner ear", "#6F382D", roughness=0.82)
    amber = solid_material("Leo refined amber iris", "#C77A16", roughness=0.24, coat=0.35)
    pupil = solid_material("Leo refined pupil", "#080503", roughness=0.24, coat=0.22)
    highlight = solid_material("Leo refined eye glint", "#FFF4DC", roughness=0.08, coat=0.55)
    nose = solid_material("Leo refined nose", "#261512", roughness=0.48, coat=0.12)
    whisker = solid_material("Leo refined whiskers", "#E9D3A8", roughness=0.72)

    body = bpy.data.objects.get("Leo_Realistic_Body")
    if body is None or body.type != "MESH":
        raise RuntimeError("Expected Leo_Realistic_Body mesh in the input sculpt")
    body.data.materials.clear()
    for material in (coat, cream, dark, inner_ear):
        body.data.materials.append(material)
    body.data.update()
    for polygon in body.data.polygons:
        center = polygon.center
        material_index = 0
        if center.x > 1.95 and 2.02 < center.z < 2.38 and abs(center.y) < 0.34:
            material_index = 1
        if center.x > 2.16 and 2.26 < center.z < 2.43 and abs(center.y) < 0.15:
            material_index = 2
        if 1.55 < center.x < 2.05 and center.z > 3.00 and abs(center.y) > 0.35:
            material_index = 3
        polygon.material_index = material_index

    # Whole globes sit inside sculpted sockets. The surrounding head surface
    # occludes the far eye in profile instead of exposing detached iris cards.
    for side, sign in (("L", 1.0), ("R", -1.0)):
        y = 0.270 * sign
        add_ellipsoid(f"Eye_Rim_{side}", (2.270, y, 2.625), (0.130, 0.125, 0.105), dark)
        add_ellipsoid(f"Iris_{side}", (2.386, y, 2.625), (0.024, 0.086, 0.080), amber)
        add_ellipsoid(f"Pupil_{side}", (2.408, y, 2.625), (0.013, 0.022, 0.052), pupil)
        add_ellipsoid(
            f"Eye_Glint_{side}",
            (2.423, y - 0.025 * sign, 2.661),
            (0.009, 0.014, 0.016),
            highlight,
            segments=24,
            rings=16,
        )

    add_ellipsoid("Nose", (2.335, 0.0, 2.305), (0.038, 0.112, 0.068), nose)

    add_curve(
        "Mouth",
        [(2.340, 0.17, 2.175), (2.365, 0.0, 2.135), (2.340, -0.17, 2.175)],
        nose,
        bevel_depth=0.012,
    )
    add_curve("Philtrum", [(2.365, 0.0, 2.285), (2.365, 0.0, 2.155)], nose, bevel_depth=0.010)

    for side, sign in (("L", 1.0), ("R", -1.0)):
        for index, z in enumerate((2.205, 2.155, 2.105)):
            start_y = 0.20 * sign
            add_curve(
                f"Whisker_{side}_{index}",
                [
                    (2.335, start_y, z + 0.08),
                    (2.310, 0.48 * sign, z + 0.08 + (index - 1) * 0.015),
                    (2.225, 0.72 * sign, z + 0.08 + (index - 1) * 0.035),
                ],
                whisker,
                bevel_depth=0.006,
            )


def convert_identity_curves_to_meshes() -> None:
    for object_ in list(bpy.context.scene.objects):
        if not object_.name.startswith(DETAIL_PREFIX) or object_.type != "CURVE":
            continue
        bpy.ops.object.select_all(action="DESELECT")
        object_.select_set(True)
        bpy.context.view_layer.objects.active = object_
        bpy.ops.object.convert(target="MESH")


def configure_source_metadata(source: Path) -> None:
    scene = bpy.context.scene
    scene["leo_realistic_pipeline_version"] = PIPELINE_VERSION
    scene["leo_asset_status"] = "realistic-identity-candidate-not-runtime-approved"
    scene["leo_identity_source"] = "project-owned sculpt derived from approved Leo turnaround"
    scene["leo_refinement_source"] = source.name
    scene["leo_next_gate"] = "combined clean sculpt turntable"
    scene.render.film_transparent = True
    scene.render.use_stamp = False
    with contextlib.suppress(TypeError):
        scene.view_settings.look = "AgX - Medium High Contrast"


def main() -> None:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    bpy.ops.wm.open_mainfile(filepath=str(source))
    remove_previous_identity_details()
    body = bpy.data.objects.get("Leo_Realistic_Body")
    if body is None or body.type != "MESH":
        raise RuntimeError("Expected Leo_Realistic_Body mesh in the input sculpt")
    smooth_body(body, args.smooth_factor, args.smooth_iterations)
    reshape_head(body)
    if args.textures_dir is not None:
        apply_turnaround_projection(body, args.textures_dir.expanduser().resolve())
    else:
        sculpt_eye_sockets(body)
        build_face()
        convert_identity_curves_to_meshes()
    configure_source_metadata(source)

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    if args.glb is not None:
        glb = args.glb.expanduser().resolve()
        glb.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=str(glb), export_format="GLB")
    print(f"LEO_REALISTIC_SOURCE={output}")


if __name__ == "__main__":
    main()
