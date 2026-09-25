"""Run using FreeCAD's matching Python, isolated from interactive documents."""
import math
import os
import time
from pathlib import Path

import FreeCAD as App
import Part
import MeshPart

from common import ROOT, OUT, BUILD, kit, sha256, write_json


def box(x, y, z, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, App.Vector(x, y, z))


def polygon_prism(points, vector):
    vertices = [App.Vector(*p) for p in points]
    return Part.Face(Part.makePolygon(vertices + [vertices[0]])).extrude(App.Vector(*vector))


def fuse(shapes):
    if len(shapes) == 1:
        return shapes[0]
    return shapes[0].multiFuse(shapes[1:]).removeSplitter()


def make_shape(p, common):
    nx, ny, h = p["nx"], p["ny"], p["body_height"]
    width, depth = nx * 8.0, ny * 8.0
    roof = p["roof_mm"]
    void_h = h - roof
    c = p["female_radial_clearance"]
    inner = 4 - common["reference_stud_diameter"] / 2 - c
    outer = box(.1, .1, 0, width - .2, depth - .2, h)
    entry, lead = common["socket_lead_in"], common["socket_lead_in_height"]
    wires = []
    for z, boundary in ((0, inner - entry), (lead, inner)):
        pts = [App.Vector(boundary, boundary, z), App.Vector(width - boundary, boundary, z),
               App.Vector(width - boundary, depth - boundary, z), App.Vector(boundary, depth - boundary, z)]
        wires.append(Part.makePolygon(pts + [pts[0]]))
    cavity = Part.makeLoft(wires, True).fuse(
        box(inner, inner, lead, width - inner * 2, depth - inner * 2, void_h - lead))
    shell = outer.cut(cavity)
    structure = [shell]
    rib = common["rib_width"]
    for ix in range(1, nx):
        structure.append(box(ix * 8 - rib / 2, inner - .02, 0,
                             rib, depth - inner * 2 + .04, void_h + .02))
    for iy in range(1, ny):
        structure.append(box(inner - .02, iy * 8 - rib / 2, 0,
                             width - inner * 2 + .04, rib, void_h + .02))
    if nx > 1 and ny > 1:
        radius = math.sqrt(32) - 2.4 - c
        for ix in range(1, nx):
            for iy in range(1, ny):
                pos = App.Vector(ix * 8, iy * 8, 0)
                tube = Part.makeCone(radius - entry, radius, lead, pos).fuse(
                    Part.makeCylinder(radius, void_h - lead + .02, pos + App.Vector(0, 0, lead)))
                tube = tube.cut(Part.makeCylinder(1.6, void_h + .03, pos))
                structure.append(tube)
    else:
        for i in range(1, max(nx, ny)):
            pos = App.Vector(4 if nx == 1 else i * 8, i * 8 if nx == 1 else 4, 0)
            structure.append(Part.makeCone(inner - entry, inner, lead, pos).fuse(
                Part.makeCylinder(inner, void_h - lead + .02, pos + App.Vector(0, 0, lead))))
    shell = fuse(structure)
    if nx > 1 and ny > 1:
        # Ribs join the outside of each tube; keep its 3.2 mm bore fully open.
        bores = [Part.makeCylinder(1.6, void_h, App.Vector(ix * 8, iy * 8, 0))
                 for ix in range(1, nx) for iy in range(1, ny)]
        shell = shell.cut(Part.makeCompound(bores)).removeSplitter()
    additions = [shell]
    if p["studs"]:
        radius = (4.8 + p["male_diameter_correction"]) / 2
        for ix in range(nx):
            for iy in range(ny):
                pos = App.Vector(4 + ix * 8, 4 + iy * 8, h - .02)
                stud = Part.makeCylinder(radius, 1.57, pos).fuse(
                    Part.makeCone(radius, radius - .25, .25, pos + App.Vector(0, 0, 1.57)))
                additions.append(stud)
    if p["kind"] == "ear":
        additions.append(polygon_prism(
            [(.1, .1, h - .02), (.1, 15.9, h - .02),
             (.1, 15.9, h + 1.6), (.1, .1, h + 9.6)], (15.8, 0, 0)))
    elif p["kind"] == "keyboard":
        for x in (2.2, 8.7):
            for i in range(10):
                additions.append(box(x, 2.1 + 4.4 * i, h - .02, 5.1, 3.1, .72))
    elif p["kind"] == "mug":
        pos = App.Vector(8, 16, h - .02)
        cup = Part.makeCylinder(6.2, 11.22, pos).cut(
            Part.makeCylinder(4.4, 12, App.Vector(8, 16, h + 1.8)))
        handle = box(6.8, 1.2, h - .02, 2.4, 10, 10.02).cut(
            box(6.6, 3.6, h + 2.4, 2.8, 5.2, 5.2))
        additions.extend([cup, handle])
    return fuse(additions)


def bounds(shape):
    b = shape.BoundBox
    return [[b.XMin, b.YMin, b.ZMin], [b.XMax, b.YMax, b.ZMax]]


def matrix(instance):
    from common import rotation_z
    r, t = rotation_z(instance["rotation_deg"]), instance["translation_mm"]
    return App.Matrix(r[0][0], r[0][1], 0, t[0],
                      r[1][0], r[1][1], 0, t[1],
                      0, 0, 1, t[2], 0, 0, 0, 1)


def main():
    data = kit()
    for folder in ("cad", "stl", "coupons", "data", "validation"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    (BUILD / "brep").mkdir(parents=True, exist_ok=True)
    # Offscreen GUI providers preserve native colors without touching an open app.
    import FreeCADGui as Gui
    Gui.setupWithoutGUI()
    doc = App.newDocument("Octodesk")
    library = doc.addObject("App::DocumentObjectGroup", "TypeLibrary")
    assembly = doc.addObject("App::DocumentObjectGroup", "Assembly")
    coupons = doc.addObject("App::DocumentObjectGroup", "FitCoupons")
    catalog, shapes = {}, {}
    source_hash = sha256(Path(__file__))
    for pid, spec in data["parts"].items():
        started = time.monotonic()
        shape = make_shape(spec, data["parameters"])
        assert shape.isValid() and len(shape.Solids) == 1 and shape.Volume > 0, pid
        shapes[pid] = shape
        shape.exportBrep(str(BUILD / "brep" / f"{pid}.brep"))
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=.06,
                                     AngularDeflection=.16, Relative=False)
        folder = "coupons" if spec.get("test_only") else "stl"
        stl = OUT / folder / f"{pid}.stl"
        mesh.write(str(stl))
        obj = doc.addObject("PartDesign::Feature", pid.replace("-", "_"))
        obj.Label = pid
        obj.Shape = shape
        obj.addProperty("App::PropertyString", "PartID").PartID = pid
        (coupons if spec.get("test_only") else library).addObject(obj)
        if obj.ViewObject:
            obj.ViewObject.Visibility = False
        catalog[pid] = {**spec, "bounds_mm": bounds(shape), "volume_mm3": shape.Volume,
                        "stl": str(stl.relative_to(OUT)), "sha256": sha256(stl),
                        "brep_valid": True, "solid_count": 1, "triangles": mesh.CountFacets,
                        "minimum_outer_wall_mm": 4 - 2.4 - spec["female_radial_clearance"] - .1,
                        "minimum_entry_wall_mm": 4 - 2.4 - spec["female_radial_clearance"] - .3,
                        "roof_bridge_span_mm": 6.8}
        print(f"{pid}: {mesh.CountFacets} triangles / {time.monotonic() - started:.1f}s", flush=True)
    assembled = []
    for inst in data["instances"]:
        obj = doc.addObject("PartDesign::Feature", inst["id"].replace("-", "_"))
        obj.Label = f'{inst["id"]} | {inst["part"]} | {inst["color"]}'
        obj.Shape = shapes[inst["part"]]
        obj.Placement = App.Placement(matrix(inst))
        obj.addProperty("App::PropertyString", "InstanceID").InstanceID = inst["id"]
        obj.addProperty("App::PropertyString", "PartID").PartID = inst["part"]
        obj.addProperty("App::PropertyInteger", "Step").Step = inst["step"]
        obj.addProperty("App::PropertyString", "ColorName").ColorName = inst["color"]
        if obj.ViewObject:
            color = data["colors"][inst["color"]]["hex"]
            obj.ViewObject.ShapeColor = tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
        assembly.addObject(obj)
        assembled.append(obj)
    doc.recompute()
    native = OUT / "cad" / "Octodesk-r1.FCStd"
    doc.saveAs(str(native))
    Part.export(assembled, str(OUT / "cad" / "Octodesk-r1.step"))
    fit_doc = App.newDocument("FitCoupons")
    fit_objects = []
    for index, pid in enumerate(p for p in data["parts"] if data["parts"][p].get("test_only")):
        obj = fit_doc.addObject("PartDesign::Feature", pid.replace("-", "_"))
        obj.Shape = shapes[pid]
        obj.Label = pid
        obj.Placement.Base = App.Vector((index % 4) * 26, (index // 4) * 26, 0)
        fit_objects.append(obj)
    fit_doc.recompute()
    fit_doc.saveAs(str(OUT / "cad" / "Fit-coupons.FCStd"))
    Part.export(fit_objects, str(OUT / "cad" / "Fit-coupons.step"))
    total = Part.makeCompound([o.Shape for o in assembled])
    result = {
        "revision": data["revision"], "freecad_version": ".".join(App.Version()[:3]),
        "generator_sha256": source_hash, "parts": catalog,
        "assembly_bounds_mm": bounds(total),
        "assembly_size_mm": [total.BoundBox.XLength, total.BoundBox.YLength, total.BoundBox.ZLength],
        "assembly_volume_mm3": total.Volume,
        "native": "cad/Octodesk-r1.FCStd", "step": "cad/Octodesk-r1.step",
    }
    write_json(OUT / "data" / "catalog.json", result)
    print("CAD_SAVED", result["assembly_size_mm"], flush=True)


if __name__ == "__main__":
    main()
