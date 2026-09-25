import itertools
import json
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

from common import OUT, kit, read_json, sha256, write_json
from package_prints import CORE


def main():
    data = kit()
    catalog = read_json(OUT / "data" / "catalog.json")
    meshes, checked = {}, []
    for pid, p in catalog["parts"].items():
        path = OUT / p["stl"]
        assert sha256(path) == p["sha256"], pid
        mesh = trimesh.load(path, force="mesh", process=True)
        assert np.isfinite(mesh.vertices).all()
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0, pid
        assert len(mesh.split(only_watertight=False)) == 1, pid
        assert mesh.area_faces.min() > 1e-9, pid
        assert np.allclose(mesh.bounds, p["bounds_mm"], atol=2e-5), pid
        volume_error = abs(mesh.volume / p["volume_mm3"] - 1)
        assert volume_error < .005, (pid, volume_error)
        unique_edges, edge_counts = np.unique(mesh.edges_sorted, axis=0, return_counts=True)
        assert np.all(edge_counts == 2), pid
        meshes[pid] = mesh
        checked.append({"part": pid, "triangles": len(mesh.faces), "watertight": True,
                        "connected_shells": 1, "all_edges_two_faces": True, "outward_winding": True,
                        "bounds_match_brep": True, "volume_error_fraction": volume_error,
                        "minimum_triangle_area_mm2": float(mesh.area_faces.min())})
    manifest = read_json(OUT / "data" / "print-manifest.json")
    namespace = {"m": CORE}
    plate_reports, occurrences = [], Counter()
    for plate in manifest["plates"] + manifest["trials"]:
        assert sha256(OUT / plate["file"]) == plate["sha256"]
        imported = trimesh.load(OUT / plate["file"], force="scene")
        assert len(imported.graph.nodes_geometry) == len(plate["slots"])
        expected_bounds = [
            np.min([slot["print_bounds_mm"][0] for slot in plate["slots"]], axis=0),
            np.max([slot["print_bounds_mm"][1] for slot in plate["slots"]], axis=0),
        ]
        assert np.allclose(imported.bounds, expected_bounds, atol=2e-5)
        with zipfile.ZipFile(OUT / plate["file"]) as archive:
            assert archive.testzip() is None
            root = ET.fromstring(archive.read("3D/3dmodel.model"))
        assert root.attrib["unit"] == "millimeter"
        resources = {o.attrib["id"]: o for o in root.findall("m:resources/m:object", namespace)}
        build = root.findall("m:build/m:item", namespace)
        assert len(build) == len(plate["slots"])
        for item, slot in zip(build, plate["slots"]):
            assert int(item.attrib["objectid"]) == slot["object_id"]
            wrapper = resources[item.attrib["objectid"]]
            assert wrapper.attrib["name"] == f"slot-{slot['slot']:03d} | {slot['part']} | {slot['color']}"
            component = wrapper.find("m:components/m:component", namespace)
            geometry = resources[component.attrib["objectid"]].find("m:mesh", namespace)
            vv = np.array([[float(v.attrib[c]) for c in ("x", "y", "z")]
                           for v in geometry.findall("m:vertices/m:vertex", namespace)])
            ff = np.array([[int(f.attrib[c]) for c in ("v1", "v2", "v3")]
                           for f in geometry.findall("m:triangles/m:triangle", namespace)])
            original = meshes[slot["part"]]
            assert np.allclose(vv, original.vertices, atol=1e-6)
            assert np.array_equal(ff, original.faces)
            transform = np.array([float(x) for x in item.attrib["transform"].split()])
            assert np.allclose(transform[:9], [1, 0, 0, 0, 1, 0, 0, 0, 1])
            assert np.allclose(transform[9:], slot["translation_mm"])
            b = original.bounds + transform[9:]
            assert np.allclose(b, slot["print_bounds_mm"], atol=2e-5)
            assert np.all(b[0, :2] >= 9.99999) and np.all(b[1, :2] <= 246.00001)
            assert abs(b[0, 2]) < 1e-6 and b[1, 2] <= 256
            if plate["assembly"]:
                occurrences[(slot["part"], slot["color"])] += 1
                expected = [i["id"] for i in data["instances"] if i["part"] == slot["part"]
                            and i["color"] == slot["color"]]
                assert slot["candidate_instances"] == expected
                assert slot["example_instance"] in expected
                for instance in expected:
                    assert {"file": plate["file"], "slot": slot["slot"]} in manifest["instance_sources"][instance]
        minimum_gap = 256
        for a, b in itertools.combinations(plate["slots"], 2):
            a0, a1 = np.array(a["print_bounds_mm"])[:, :2]
            b0, b1 = np.array(b["print_bounds_mm"])[:, :2]
            gap = max(*(b0 - a1), *(a0 - b1))
            assert gap >= 9.99999, (plate["file"], a["slot"], b["slot"], gap)
            minimum_gap = min(minimum_gap, float(gap))
        plate_reports.append({"file": plate["file"], "slots": len(build),
                              "independent_build_items": True, "mesh_matches_stl": True,
                              "independent_trimesh_scene_import_count_and_bounds": True,
                              "unit_mm": True, "minimum_bbox_gap_mm": minimum_gap,
                              "bed": "256x256 with 10 mm nominal edge margin; no toolpath qualification"})
    bom = Counter({(r["part"], r["color"]): r["quantity"] for r in data["bom"]})
    assembled = Counter((i["part"], i["color"]) for i in data["instances"])
    assert bom == assembled == occurrences
    assert set(manifest["instance_sources"]) == {i["id"] for i in data["instances"]}
    for inst in data["instances"]:
        expected_sources = [{"file": p["file"], "slot": s["slot"]}
                            for p in manifest["plates"] for s in p["slots"]
                            if s["part"] == inst["part"] and s["color"] == inst["color"]]
        assert manifest["instance_sources"][inst["id"]] == expected_sources
    write_json(OUT / "validation" / "meshes-and-plates.json", {
        "status": "PASS", "types": checked, "plates": plate_reports,
        "assembly_bom_equals_3mf_equals_instances": sum(occurrences.values()),
        "trial_slots_excluded_from_assembly": sum(len(p["slots"]) for p in manifest["trials"]),
        "bidirectional_mapping_complete": True, "commercial_compatibility_tested": False,
        "sliced": False, "profile_exclusion_zones_checked": False,
    })
    print("MESH_3MF_VALIDATED", len(checked), "types,", sum(occurrences.values()), "assembly slots")


if __name__ == "__main__":
    main()
