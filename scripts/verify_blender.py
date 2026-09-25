import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, kit, read_json, write_json


def main():
    data, catalog = kit(), read_json(OUT / "data" / "catalog.json")
    generation = read_json(OUT / "validation" / "blender-generation.json")
    scene = bpy.context.scene
    assert scene.render.filepath.startswith("//"), "Native scene render output must be relative."
    objects = {o.name: o for o in scene.objects if "part_id" in o}
    assert len(objects) == len(data["instances"])
    scene.frame_set(generation["assembly_end_frame"])
    bounds = []
    for inst in data["instances"]:
        obj = objects[inst["id"]]
        spec = catalog["parts"][inst["part"]]
        assert obj["part_id"] == inst["part"]
        assert obj["color_id"] == inst["color"]
        assert obj["stl_sha256"] == spec["sha256"]
        assert len(obj.data.polygons) == spec["triangles"]
        assert max(abs(obj.location[i] * 1000 - inst["translation_mm"][i]) for i in range(3)) < .00005
        assert abs(obj.rotation_euler.z - math.radians(inst["rotation_deg"])) < 1e-6
        assert obj.material_slots[0].material.name == inst["color"]
        local = [Vector(v) * 1000 for v in obj.bound_box]
        minimum = [min(v[i] for v in local) for i in range(3)]
        maximum = [max(v[i] for v in local) for i in range(3)]
        assert max(abs(a - b) for a, b in zip(minimum + maximum, sum(spec["bounds_mm"], []))) < .00005
        bounds.extend([obj.matrix_world @ Vector(v) * 1000 for v in obj.bound_box])
    global_bounds = [[min(v[i] for v in bounds) for i in range(3)], [max(v[i] for v in bounds) for i in range(3)]]
    assert max(abs(a - b) for a, b in zip(sum(global_bounds, []), sum(catalog["assembly_bounds_mm"], []))) < .0001
    scene.frame_set(1)
    assert all(o.hide_render for o in objects.values())
    for step in generation["frame_steps"]:
        scene.frame_set(step["end"])
        visible = {o.name for o in objects.values() if not o.hide_render}
        expected = {i["id"] for i in data["instances"] if i["step"] <= step["step"]}
        assert visible == expected, step["step"]
    write_json(OUT / "validation" / "blender.json", {
        "status": "PASS", "native_blend_reopened": True, "instances": len(objects),
        "stl_hashes_triangles_local_bounds_materials_match": True,
        "mm_to_m_verified": .001, "completed_global_bounds_mm": global_bounds,
        "empty_frame_verified": 1, "step_end_frames_verified": len(generation["frame_steps"]),
        "camera_turntable_frames": 48, "physical_simulation": False,
        "render_output_relative": True,
    })
    print("BLEND_VALIDATED", len(objects), "instances")


if __name__ == "__main__":
    main()
