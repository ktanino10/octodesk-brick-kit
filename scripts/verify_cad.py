import itertools
import time

import FreeCAD as App
import Part

from common import OUT, BUILD, kit, read_json, write_json
from freecad_build import bounds, matrix


def xy_overlap(a, b):
    return min(a.XMax, b.XMax) - max(a.XMin, b.XMin) > 1e-6 and (
        min(a.YMax, b.YMax) - max(a.YMin, b.YMin) > 1e-6)


def xyz_overlap(a, b):
    return xy_overlap(a, b) and min(a.ZMax, b.ZMax) - max(a.ZMin, b.ZMin) > 1e-6


def close(a, b, tolerance=1e-5):
    assert len(a) == len(b)
    assert max(abs(x - y) for x, y in zip(a, b)) < tolerance, (a, b)


def main():
    started = time.monotonic()
    data, catalog = kit(), read_json(OUT / "data" / "catalog.json")
    shapes = {}
    for pid, p in data["parts"].items():
        shape = Part.Shape()
        shape.read(str(BUILD / "brep" / f"{pid}.brep"))
        assert shape.isValid() and len(shape.Solids) == 1 and shape.Volume > 0, pid
        # All receiving stud centers must remain open from the bottom through the engagement depth.
        for x in range(p["nx"]):
            for y in range(p["ny"]):
                for z in (.02, .3, 1.0, 1.8, 2.0):
                    assert not shape.isInside(App.Vector(4 + x * 8, 4 + y * 8, z), 1e-7, True), (pid, x, y, z)
        if p["nx"] > 1 and p["ny"] > 1:
            for x in range(1, p["nx"]):
                for y in range(1, p["ny"]):
                    assert not shape.isInside(App.Vector(8 * x, 8 * y, .02), 1e-7, True)
        shapes[pid] = shape
    doc = App.openDocument(str(OUT / "cad" / "Octodesk-r1.FCStd"))
    native = {o.InstanceID: o for o in doc.Objects if "InstanceID" in o.PropertiesList}
    assert len(native) == len(data["instances"])
    placed = {}
    for inst in data["instances"]:
        shape = shapes[inst["part"]].copy()
        shape.Placement = App.Placement(matrix(inst))
        other = native[inst["id"]].Shape
        close(sum(bounds(shape), []), sum(bounds(other), []))
        assert abs(shape.Volume - other.Volume) < 1e-4
        assert other.isValid()
        placed[inst["id"]] = shape
    step_doc = App.newDocument("ImportedStep")
    Part.insert(str(OUT / "cad" / "Octodesk-r1.step"), step_doc.Name)
    step_shapes = [o.Shape for o in step_doc.Objects if hasattr(o, "Shape") and o.Shape.Solids]
    step_solids = [solid for shape in step_shapes for solid in shape.Solids]
    assert len(step_solids) == len(placed), len(step_solids)
    expected = sorted((round(s.Volume, 3), *[round(v, 3) for v in sum(bounds(s), [])])
                      for s in placed.values())
    actual = sorted((round(s.Volume, 3), *[round(v, 3) for v in sum(bounds(s), [])])
                    for s in step_solids)
    assert expected == actual, "STEP per-solid volume/bounds correspondence"
    intersections = []
    candidates = 0
    for (ida, a), (idb, b) in itertools.combinations(placed.items(), 2):
        if xyz_overlap(a.BoundBox, b.BoundBox):
            candidates += 1
            common = a.common(b)
            if common.Volume > 1e-6:
                intersections.append({"a": ida, "b": idb, "volume_mm3": common.Volume})
    insertion_samples, monotone_pairs = 0, 0
    for index, inst in enumerate(data["instances"]):
        shape = placed[inst["id"]]
        z = inst["anchor_mm"][2]
        for prior in data["instances"][:index]:
            lower = placed[prior["id"]]
            if not xy_overlap(shape.BoundBox, lower.BoundBox):
                continue
            # Above the landing plane only aligned studs may occupy the insertion column.
            assert lower.BoundBox.ZMax <= z + 1.80001, (inst["id"], prior["id"], "blocked vertical approach")
            if lower.BoundBox.ZMax <= z:
                continue
            monotone_pairs += 1
            for dz in (.15, .5, 1.0, 1.79, 2.0, 8.0, 40.0):
                moved = shape.copy()
                moved.translate(App.Vector(0, 0, dz))
                overlap = moved.common(lower).Volume
                assert overlap < 1e-6, (inst["id"], prior["id"], dz, overlap)
                insertion_samples += 1
    adjacency = {i["id"]: set() for i in data["instances"]}
    connection_count, min_studs = 0, 999
    for inst in data["instances"]:
        studs = 0
        for con in inst["connections"]:
            adjacency[inst["id"]].add(con["lower"])
            adjacency[con["lower"]].add(inst["id"])
            connection_count += 1
            studs += len(con["stud_centers_mm"])
        if not inst["foundation"]:
            assert studs >= 2, inst["id"]
            min_studs = min(min_studs, studs)
    reached, pending = set(), [data["instances"][0]["id"]]
    while pending:
        node = pending.pop()
        if node not in reached:
            reached.add(node)
            pending.extend(adjacency[node] - reached)
    assert len(reached) == len(adjacency)
    report = {
        "status": "PASS" if not intersections else "FAIL",
        "native_reopened": True, "step_reimported": True,
        "valid_single_solid_types": len(shapes), "native_instances": len(native),
        "step_solids": len(step_solids), "step_per_solid_bounds_volume_match": True,
        "pair_count": len(placed) * (len(placed) - 1) // 2, "bbox_candidate_pairs": candidates,
        "intersections": intersections, "interference_tolerance_mm3": 1e-6,
        "insertion_sample_count": insertion_samples, "monotone_engagement_pairs": monotone_pairs,
        "vertical_sweep_argument": "For every XY-overlapping earlier part, max Z <= landing Z + 1.8. "
            "Only aligned stud tips enter; open receivers have 2.2 mm minimum roof clearance and wider "
            "lead-ins. Non-stud solids are below landing Z. Intermediate engagement samples also checked.",
        "connected_instances": len(reached), "connections": connection_count,
        "minimum_engaged_studs": min_studs,
        "hand_access": "Assembly order keeps head off until cup and neck are fitted. Keyboard is last "
            "with 16 mm clearance from head and 24 mm from monitor. Not a hand/force simulation.",
        "physical_qualification": False, "elapsed_seconds": round(time.monotonic() - started, 1),
        "assembly_bounds_mm": catalog["assembly_bounds_mm"],
    }
    write_json(OUT / "validation" / "cad.json", report)
    assert not intersections, intersections[:10]
    print("CAD_VALIDATED", report["elapsed_seconds"], "seconds")


if __name__ == "__main__":
    main()
