"""Create an isolated quadruped deformation rig for realistic Leo.

The rig is a mechanical smoke-test asset, not a runtime replacement. It uses
Blender's heat weights on the approved manifold quad candidate and records
coverage for every deform bone before saving.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import bmesh
import bpy
from mathutils import Vector

PIPELINE_VERSION = 1
RIG_NAME = "RIG_Leo_Realistic"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--body-name", default="Leo_Realistic_Body")
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(args)


def remove_previous_rig(body: bpy.types.Object) -> None:
    for modifier in list(body.modifiers):
        if modifier.type == "ARMATURE":
            body.modifiers.remove(modifier)
    body.parent = None
    body.vertex_groups.clear()
    for object_ in list(bpy.context.scene.objects):
        if object_.name == RIG_NAME:
            bpy.data.objects.remove(object_, do_unlink=True)


def create_rig() -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0.0, 0.0, 0.0))
    rig = bpy.context.object
    rig.name = RIG_NAME
    rig.data.name = f"{RIG_NAME}_Data"
    for existing in list(rig.data.edit_bones):
        rig.data.edit_bones.remove(existing)

    bones: dict[str, bpy.types.EditBone] = {}

    def bone(
        name: str,
        head: tuple[float, float, float],
        tail: tuple[float, float, float],
        parent: str | None = None,
        *,
        deform: bool = True,
    ) -> None:
        result = rig.data.edit_bones.new(name)
        result.head = head
        result.tail = tail
        result.use_deform = deform
        result.envelope_distance = 0.28
        result.head_radius = 0.24
        result.tail_radius = 0.18
        if parent is not None:
            result.parent = bones[parent]
        bones[name] = result

    bone("root", (0.0, 0.0, 0.10), (0.0, 0.0, 0.62), deform=False)
    bone("pelvis", (-1.10, 0.0, 1.72), (-0.45, 0.0, 1.92), "root")
    bone("spine.01", (-0.45, 0.0, 1.92), (0.40, 0.0, 2.02), "pelvis")
    bone("spine.02", (0.40, 0.0, 2.02), (1.05, 0.0, 2.18), "spine.01")
    bone("neck", (1.05, 0.0, 2.18), (1.58, 0.0, 2.65), "spine.02")
    bone("head", (1.58, 0.0, 2.65), (2.28, 0.0, 2.78), "neck")

    for side, sign in (("L", 1.0), ("R", -1.0)):
        lateral = 0.42 * sign
        bone(
            f"foreleg_upper.{side}",
            (1.02, lateral, 2.04),
            (1.08, lateral, 1.20),
            "spine.02",
        )
        bone(
            f"foreleg_lower.{side}",
            (1.08, lateral, 1.20),
            (1.15, lateral, 0.46),
            f"foreleg_upper.{side}",
        )
        bone(
            f"front_paw.{side}",
            (1.15, lateral, 0.46),
            (1.32, lateral, 0.13),
            f"foreleg_lower.{side}",
        )
        bone(
            f"hind_thigh.{side}",
            (-1.05, lateral, 1.96),
            (-1.02, lateral, 1.18),
            "pelvis",
        )
        bone(
            f"hind_shin.{side}",
            (-1.02, lateral, 1.18),
            (-1.28, lateral, 0.52),
            f"hind_thigh.{side}",
        )
        bone(
            f"hind_paw.{side}",
            (-1.28, lateral, 0.52),
            (-1.02, lateral, 0.13),
            f"hind_shin.{side}",
        )

    bone("tail.01", (-1.52, 0.04, 2.12), (-1.82, 0.08, 1.72), "pelvis")
    bone("tail.02", (-1.82, 0.08, 1.72), (-2.04, 0.12, 1.27), "tail.01")
    bone("tail.03", (-2.04, 0.12, 1.27), (-2.27, 0.18, 0.92), "tail.02")
    bone("tail.04", (-2.27, 0.18, 0.92), (-2.50, 0.22, 0.78), "tail.03")

    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    rig.data.display_type = "OCTAHEDRAL"
    rig.display_type = "WIRE"
    rig.hide_render = True
    rig["rig_version"] = PIPELINE_VERSION
    rig["rig_contract"] = "quadruped root/pelvis/spine/neck/head, three-bone limbs, four-bone tail"
    return rig


def bind_heat_weights(body: bpy.types.Object, rig: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    result = bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    if "FINISHED" not in result:
        raise RuntimeError(f"automatic armature binding failed: {result}")


def smoothstep(minimum: float, maximum: float, value: float) -> float:
    if value <= minimum:
        return 0.0
    if value >= maximum:
        return 1.0
    normalized = (value - minimum) / (maximum - minimum)
    return normalized * normalized * (3.0 - 2.0 * normalized)


def retain_above(value: float, center: float, width: float) -> float:
    return smoothstep(center - width, center + width, value)


def retain_below(value: float, center: float, width: float) -> float:
    return 1.0 - retain_above(value, center, width)


def attenuate_weight_to_region(
    body: bpy.types.Object,
    source_name: str,
    fallback_name: str,
    retention: Callable[[Vector], float],
) -> None:
    source = body.vertex_groups[source_name]
    fallback = body.vertex_groups[fallback_name]
    for vertex in body.data.vertices:
        try:
            weight = source.weight(vertex.index)
        except RuntimeError:
            continue
        retained_weight = weight * max(0.0, min(1.0, retention(vertex.co)))
        transferred_weight = weight - retained_weight
        if transferred_weight <= 1e-6:
            continue
        try:
            fallback_weight = fallback.weight(vertex.index)
        except RuntimeError:
            fallback_weight = 0.0
        if retained_weight <= 1e-6:
            source.remove([vertex.index])
        else:
            source.add([vertex.index], retained_weight, "REPLACE")
        fallback.add([vertex.index], fallback_weight + transferred_weight, "REPLACE")


def localize_deform_weights(body: bpy.types.Object) -> None:
    attenuate_weight_to_region(
        body,
        "head",
        "neck",
        lambda coordinate: (
            retain_above(coordinate.x, 1.25, 0.30) * retain_above(coordinate.z, 1.95, 0.30)
        ),
    )
    attenuate_weight_to_region(
        body,
        "neck",
        "spine.02",
        lambda coordinate: (
            retain_above(coordinate.x, 0.72, 0.36) * retain_above(coordinate.z, 1.55, 0.34)
        ),
    )

    for side, sign in (("L", 1.0), ("R", -1.0)):
        side_retention = (
            (lambda coordinate: retain_above(coordinate.y, -0.08, 0.34))
            if sign > 0
            else (lambda coordinate: retain_below(coordinate.y, 0.08, 0.34))
        )
        attenuate_weight_to_region(
            body,
            f"front_paw.{side}",
            f"foreleg_lower.{side}",
            lambda coordinate, side_retention=side_retention: (
                retain_above(coordinate.x, 0.55, 0.28)
                * retain_below(coordinate.z, 0.72, 0.26)
                * side_retention(coordinate)
            ),
        )
        attenuate_weight_to_region(
            body,
            f"foreleg_lower.{side}",
            f"foreleg_upper.{side}",
            lambda coordinate, side_retention=side_retention: (
                retain_above(coordinate.x, 0.52, 0.32)
                * retain_below(coordinate.z, 1.52, 0.36)
                * side_retention(coordinate)
            ),
        )
        attenuate_weight_to_region(
            body,
            f"foreleg_upper.{side}",
            "spine.02",
            lambda coordinate, side_retention=side_retention: (
                retain_above(coordinate.x, 0.48, 0.42)
                * retain_below(coordinate.z, 2.38, 0.42)
                * side_retention(coordinate)
            ),
        )
        attenuate_weight_to_region(
            body,
            f"hind_paw.{side}",
            f"hind_shin.{side}",
            lambda coordinate, side_retention=side_retention: (
                retain_below(coordinate.x, -0.52, 0.28)
                * retain_below(coordinate.z, 0.74, 0.26)
                * side_retention(coordinate)
            ),
        )
        attenuate_weight_to_region(
            body,
            f"hind_shin.{side}",
            f"hind_thigh.{side}",
            lambda coordinate, side_retention=side_retention: (
                retain_below(coordinate.x, -0.48, 0.32)
                * retain_below(coordinate.z, 1.48, 0.36)
                * side_retention(coordinate)
            ),
        )
        attenuate_weight_to_region(
            body,
            f"hind_thigh.{side}",
            "pelvis",
            lambda coordinate, side_retention=side_retention: (
                retain_below(coordinate.x, -0.42, 0.42)
                * retain_below(coordinate.z, 2.45, 0.42)
                * side_retention(coordinate)
            ),
        )

    for source_name, fallback_name, maximum_x in (
        ("tail.04", "tail.03", -2.15),
        ("tail.03", "tail.02", -1.90),
        ("tail.02", "tail.01", -1.65),
        ("tail.01", "pelvis", -1.35),
    ):
        attenuate_weight_to_region(
            body,
            source_name,
            fallback_name,
            lambda coordinate, maximum_x=maximum_x: retain_below(coordinate.x, maximum_x, 0.28),
        )


def limit_deform_weights(body: bpy.types.Object, rig: bpy.types.Object, limit: int = 4) -> None:
    deform_bones = {bone.name for bone in rig.data.bones if bone.use_deform}
    group_by_index = {group.index: group for group in body.vertex_groups}
    for vertex in body.data.vertices:
        influences = [
            (group_by_index[element.group], element.weight)
            for element in vertex.groups
            if group_by_index[element.group].name in deform_bones and element.weight > 1e-6
        ]
        influences.sort(key=lambda item: item[1], reverse=True)
        retained = influences[:limit]
        for group, _weight in influences[limit:]:
            group.remove([vertex.index])
        total = sum(weight for _group, weight in retained)
        if total <= 0:
            continue
        for group, weight in retained:
            group.add([vertex.index], weight / total, "REPLACE")


def weight_report(body: bpy.types.Object, rig: bpy.types.Object) -> dict[str, Any]:
    deform_bones = {bone.name for bone in rig.data.bones if bone.use_deform}
    group_by_index = {group.index: group.name for group in body.vertex_groups}
    counts = {name: 0 for name in deform_bones}
    unweighted_vertices = 0
    excessive_influence_vertices = 0
    maximum_influences = 0
    for vertex in body.data.vertices:
        influences = [
            element
            for element in vertex.groups
            if group_by_index.get(element.group) in deform_bones and element.weight > 1e-6
        ]
        if not influences:
            unweighted_vertices += 1
        if len(influences) > 4:
            excessive_influence_vertices += 1
        maximum_influences = max(maximum_influences, len(influences))
        for element in influences:
            counts[group_by_index[element.group]] += 1
    empty_groups = sorted(name for name, count in counts.items() if count == 0)
    armature_modifiers = [modifier for modifier in body.modifiers if modifier.type == "ARMATURE"]
    return {
        "deform_bone_count": len(deform_bones),
        "vertex_group_count": len(body.vertex_groups),
        "weighted_vertices_by_bone": dict(sorted(counts.items())),
        "empty_deform_groups": empty_groups,
        "unweighted_vertices": unweighted_vertices,
        "maximum_influences_per_vertex": maximum_influences,
        "vertices_over_four_influences": excessive_influence_vertices,
        "armature_modifier_count": len(armature_modifiers),
        "armature_modifier_target": (
            armature_modifiers[0].object.name if len(armature_modifiers) == 1 else None
        ),
    }


def topology_report(body: bpy.types.Object) -> dict[str, Any]:
    mesh = bmesh.new()
    mesh.from_mesh(body.data)
    face_sides = {
        str(side_count): sum(1 for face in mesh.faces if len(face.verts) == side_count)
        for side_count in sorted({len(face.verts) for face in mesh.faces})
    }
    result = {
        "vertices": len(mesh.verts),
        "edges": len(mesh.edges),
        "faces": len(mesh.faces),
        "face_sides": face_sides,
        "boundary_edges": sum(1 for edge in mesh.edges if edge.is_boundary),
        "nonmanifold_edges": sum(1 for edge in mesh.edges if not edge.is_manifold),
    }
    mesh.free()
    return result


def main() -> None:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    bpy.ops.wm.open_mainfile(filepath=str(source))
    body = bpy.data.objects.get(args.body_name)
    if body is None or body.type != "MESH":
        raise RuntimeError(f"Expected mesh object {args.body_name!r}")
    remove_previous_rig(body)
    rig = create_rig()
    bind_heat_weights(body, rig)
    localize_deform_weights(body)
    limit_deform_weights(body, rig)
    weights = weight_report(body, rig)
    topology = topology_report(body)
    errors: list[str] = []
    if weights["unweighted_vertices"]:
        errors.append(f"{weights['unweighted_vertices']} vertices have no deform weight")
    if weights["empty_deform_groups"]:
        errors.append(f"empty deform groups: {weights['empty_deform_groups']}")
    if weights["vertices_over_four_influences"]:
        errors.append(f"{weights['vertices_over_four_influences']} vertices exceed four influences")
    if weights["armature_modifier_count"] != 1:
        errors.append(f"expected one armature modifier, found {weights['armature_modifier_count']}")
    if weights["armature_modifier_target"] != RIG_NAME:
        errors.append(f"armature modifier does not target {RIG_NAME}")
    if topology["face_sides"] != {"4": topology["faces"]}:
        errors.append(f"bound mesh is not all-quads: {topology['face_sides']}")
    if topology["boundary_edges"] or topology["nonmanifold_edges"]:
        errors.append(
            "bound mesh lost manifold topology: "
            f"boundary={topology['boundary_edges']}, "
            f"nonmanifold={topology['nonmanifold_edges']}"
        )

    report = {
        "schema_version": 1,
        "ok": not errors,
        "runtime_replacement": False,
        "source": source.name,
        "output": output.name,
        "generator": {
            "blender": bpy.app.version_string,
            "script": "tools/blender/rig_realistic_leo.py",
            "pipeline_version": PIPELINE_VERSION,
        },
        "rig": {
            "name": rig.name,
            "bone_count": len(rig.data.bones),
            "bones": [bone.name for bone in rig.data.bones],
        },
        "binding_method": {
            "initial_weights": "Blender automatic heat weights",
            "localization": "smooth anatomical falloff transfer",
            "maximum_influences_per_vertex": 4,
        },
        "topology": topology,
        "weights": weights,
        "errors": errors,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit(f"realistic-rig mechanical QA failed: {errors}")

    scene = bpy.context.scene
    scene["leo_realistic_rig_version"] = PIPELINE_VERSION
    scene["leo_asset_status"] = "deformation-rig-candidate-not-runtime-approved"
    scene["leo_rig_source"] = source.name
    scene["leo_next_gate"] = "quadruped joint deformation visual QA"
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    print(f"LEO_REALISTIC_RIG={output}")
    print(f"LEO_REALISTIC_RIG_QA={report_path}")


if __name__ == "__main__":
    main()
