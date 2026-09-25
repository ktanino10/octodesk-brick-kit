import csv
import json
import zipfile
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

import numpy as np
import trimesh

from common import OUT, kit, read_json, sha256, write_json

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
ET.register_namespace("", CORE)


def xml_tag(name):
    return f"{{{CORE}}}{name}"


def shelf_pack(items, catalog):
    pages, page = [], []
    x = y = 10.0
    row_height = 0
    ordered = sorted(items, key=lambda i: (
        -(catalog[i["part"]]["bounds_mm"][1][1] - catalog[i["part"]]["bounds_mm"][0][1]),
        -(catalog[i["part"]]["bounds_mm"][1][0] - catalog[i["part"]]["bounds_mm"][0][0]),
        i.get("example_instance", "")))
    for item in ordered:
        lower, upper = np.array(catalog[item["part"]]["bounds_mm"])
        size = upper - lower
        assert size[0] <= 236 and size[1] <= 236 and size[2] <= 256
        if x + size[0] > 246:
            x, y, row_height = 10.0, y + row_height + 10, 0
        if y + size[1] > 246:
            pages.append(page)
            page, x, y, row_height = [], 10.0, 10.0, 0
        page.append({**item, "slot": len(page) + 1,
                     "translation_mm": [float(x - lower[0]), float(y - lower[1]), float(-lower[2])],
                     "rotation_deg": 0,
                     "print_bounds_mm": [[float(x), float(y), 0],
                                         [float(x + size[0]), float(y + size[1]), float(size[2])]]})
        x += size[0] + 10
        row_height = max(row_height, size[1])
    if page:
        pages.append(page)
    return pages


def write_3mf(path, slots, catalog, colors):
    path.parent.mkdir(parents=True, exist_ok=True)
    model = ET.Element(xml_tag("model"), {"unit": "millimeter", "xml:lang": "en-US"})
    ET.SubElement(model, xml_tag("metadata"), {"name": "Title"}).text = path.name
    ET.SubElement(model, xml_tag("metadata"), {"name": "Description"}).text = (
        "NOT_SLICED | P1S 0.2 mm nozzle PLA | geometry only | independent build items | "
        "physical fit unverified | slot order equals manifest")
    resources = ET.SubElement(model, xml_tag("resources"))
    materials = ET.SubElement(resources, xml_tag("basematerials"), {"id": "1"})
    palette = list(colors)
    for key in palette:
        ET.SubElement(materials, xml_tag("base"),
                      {"name": key, "displaycolor": colors[key]["hex"].upper() + "FF"})
    mesh_ids = {}
    next_id = 2
    for pid, color in sorted(set((s["part"], s["color"]) for s in slots)):
        mesh = trimesh.load(OUT / catalog[pid]["stl"], force="mesh", process=True)
        obj = ET.SubElement(resources, xml_tag("object"),
                            {"id": str(next_id), "type": "model", "name": f"{pid} {color}",
                             "pid": "1", "pindex": str(palette.index(color))})
        mesh_ids[(pid, color)] = next_id
        next_id += 1
        mesh_element = ET.SubElement(obj, xml_tag("mesh"))
        vertices = ET.SubElement(mesh_element, xml_tag("vertices"))
        for v in mesh.vertices:
            ET.SubElement(vertices, xml_tag("vertex"), dict(zip(("x", "y", "z"), (f"{n:.7f}" for n in v))))
        triangles = ET.SubElement(mesh_element, xml_tag("triangles"))
        for f in mesh.faces:
            ET.SubElement(triangles, xml_tag("triangle"), dict(zip(("v1", "v2", "v3"), map(str, f))))
    build = ET.SubElement(model, xml_tag("build"))
    for slot in slots:
        object_id = next_id
        next_id += 1
        obj = ET.SubElement(resources, xml_tag("object"), {
            "id": str(object_id), "type": "model",
            "name": f"slot-{slot['slot']:03d} | {slot['part']} | {slot['color']}"})
        components = ET.SubElement(obj, xml_tag("components"))
        ET.SubElement(components, xml_tag("component"),
                      {"objectid": str(mesh_ids[(slot["part"], slot["color"])])})
        t = slot["translation_mm"]
        ET.SubElement(build, xml_tag("item"), {"objectid": str(object_id),
                      "transform": f"1 0 0 0 1 0 0 0 1 {t[0]:.7f} {t[1]:.7f} {t[2]:.7f}"})
        slot["object_id"] = object_id
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        '</Types>')
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("3D/3dmodel.model", ET.tostring(model, encoding="utf-8", xml_declaration=True))


def csv_file(path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    data = kit()
    catalog = read_json(OUT / "data" / "catalog.json")["parts"]
    grouped = defaultdict(list)
    candidates = defaultdict(list)
    for inst in data["instances"]:
        candidates[(inst["part"], inst["color"])].append(inst["id"])
    for inst in data["instances"]:
        grouped[inst["color"]].append({"part": inst["part"], "color": inst["color"],
                                       "example_instance": inst["id"],
                                       "candidate_instances": candidates[(inst["part"], inst["color"])]})
    plates = []
    for color, items in grouped.items():
        for index, slots in enumerate(shelf_pack(items, catalog), 1):
            file = f"plates/O-{color}-{index:02d}-NOT_SLICED.3mf"
            write_3mf(OUT / file, slots, catalog, data["colors"])
            plates.append({"file": file, "color": color, "assembly": True,
                           "print_order": len(plates) + 1, "slots": slots, "sha256": sha256(OUT / file)})
    trials = []
    for batch in data["trial_batches"]:
        items = [{"part": row["part"], "color": "white", "candidate_instances": [],
                  "example_instance": None}
                 for row in batch["parts"] for _ in range(row["quantity"])]
        pages = shelf_pack(items, catalog)
        assert len(pages) == 1
        file = f"coupons/{batch['id']}-NOT_SLICED.3mf"
        write_3mf(OUT / file, pages[0], catalog, data["colors"])
        trials.append({"file": file, "assembly": False, "title": batch["title"],
                       "slots": pages[0], "sha256": sha256(OUT / file)})
    reverse = defaultdict(list)
    for plate in plates:
        for slot in plate["slots"]:
            for candidate in slot["candidate_instances"]:
                reverse[candidate].append({"file": plate["file"], "slot": slot["slot"]})
    manifest = {"revision": data["revision"], "status": "NOT_SLICED",
                "bed_mm": [256, 256, 256], "edge_margin_mm": 10, "part_gap_mm": 10,
                "brim_allowance_mm_per_part": 4,
                "note": "実プレートの除外領域・支持材・brim・ツールパスは未検証。印刷順と工程は別。",
                "interchangeable": True, "plates": plates, "trials": trials,
                "instance_sources": dict(reverse)}
    write_json(OUT / "data" / "print-manifest.json", manifest)
    csv_file(OUT / "data" / "bom.csv", ["part", "color", "quantity", "stl", "print_sources"],
             [[r["part"], r["color"], r["quantity"], catalog[r["part"]]["stl"],
               "; ".join(p["file"] for p in plates if any(
                   s["part"] == r["part"] and s["color"] == r["color"] for s in p["slots"]))]
              for r in data["bom"]])
    csv_file(OUT / "data" / "instances.csv",
             ["instance", "part", "color", "step", "role", "x", "y", "z", "rotation_z", "supporting_instances"],
             [[i["id"], i["part"], i["color"], i["step"], i["role"],
               *i["translation_mm"], i["rotation_deg"], ";".join(c["lower"] for c in i["connections"])]
              for i in data["instances"]])
    csv_file(OUT / "data" / "plate-to-assembly.csv",
             ["file", "slot", "part", "color", "example_instance", "all_interchangeable_candidates"],
             [[p["file"], s["slot"], s["part"], s["color"], s["example_instance"],
               ";".join(s["candidate_instances"])] for p in plates for s in p["slots"]])
    csv_file(OUT / "data" / "trials-only.csv", ["file", "slot", "part", "assembly_bom"],
             [[p["file"], s["slot"], s["part"], "EXCLUDED"] for p in trials for s in p["slots"]])
    print("PLATES_SAVED", len(plates), "assembly slots", sum(len(p["slots"]) for p in plates))


if __name__ == "__main__":
    main()
