"""Native BREP documents with explicit color data, without initializing a GUI."""
import FreeCAD as App
import Part

from common import OUT, BUILD, kit, read_json, sha256, write_json
from freecad_build import matrix, bounds


def main():
    data, catalog = kit(), read_json(OUT / "data" / "catalog.json")
    shapes = {}
    for pid in data["parts"]:
        shape = Part.Shape()
        shape.read(str(BUILD / "brep" / f"{pid}.brep"))
        shapes[pid] = shape
    doc = App.newDocument("OctodeskAssembly")
    steps = {}
    for step in data["steps"]:
        group = doc.addObject("App::DocumentObjectGroup", f"Step_{step['number']:02d}")
        group.Label = f"{step['number']:02d} | {step['title']}"
        steps[step["number"]] = group
    for inst in data["instances"]:
        obj = doc.addObject("PartDesign::Feature", inst["id"].replace("-", "_"))
        obj.Shape = shapes[inst["part"]]
        obj.Placement = App.Placement(matrix(inst))
        obj.Label = f"{inst['id']} | {inst['part']} | {inst['color']} | {inst['role']}"
        for name, value in (("InstanceID", inst["id"]), ("PartID", inst["part"]),
                            ("ColorName", inst["color"]), ("SourceSTL", catalog["parts"][inst["part"]]["stl"])):
            obj.addProperty("App::PropertyString", name, "Kit")
            setattr(obj, name, value)
        obj.addProperty("App::PropertyInteger", "Step", "Kit").Step = inst["step"]
        rgb = data["colors"][inst["color"]]["hex"]
        obj.addProperty("App::PropertyColor", "PartColor", "Kit").PartColor = tuple(
            int(rgb[i:i + 2], 16) / 255 for i in (1, 3, 5))
        steps[inst["step"]].addObject(obj)
    doc.recompute()
    file = OUT / "cad" / "Octodesk-r1.FCStd"
    doc.saveAs(str(file))
    App.closeDocument(doc.Name)
    reopened = App.openDocument(str(file))
    objects = {o.InstanceID: o for o in reopened.Objects if "InstanceID" in o.PropertiesList}
    assert len(objects) == len(data["instances"])
    assert len([o for o in reopened.Objects if "Shape" in o.PropertiesList]) == len(objects)
    for inst in data["instances"]:
        obj = objects[inst["id"]]
        expected = shapes[inst["part"]].copy()
        expected.Placement = App.Placement(matrix(inst))
        assert max(abs(a - b) for a, b in zip(sum(bounds(obj.Shape), []), sum(bounds(expected), []))) < 1e-6
        assert obj.Shape.isValid() and len(obj.Shape.Solids) == 1
        assert abs(obj.Shape.Volume - catalog["parts"][inst["part"]]["volume_mm3"]) < 1e-5
        assert obj.ColorName == inst["color"] and obj.PartID == inst["part"] and obj.Step == inst["step"]
        rgb = data["colors"][inst["color"]]["hex"]
        assert max(abs(obj.PartColor[j] - int(rgb[i:i+2], 16) / 255) for j, i in enumerate((1,3,5))) < 1e-6
    App.closeDocument(reopened.Name)
    library = App.newDocument("TypeLibrary")
    for index, (pid, spec) in enumerate(data["parts"].items()):
        obj = library.addObject("PartDesign::Feature", pid.replace("-", "_"))
        obj.Shape = shapes[pid]
        obj.Placement.Base = App.Vector((index % 5) * 88, (index // 5) * 96, 0)
        obj.Label = pid + (" | TEST ONLY" if spec.get("test_only") else " | PRODUCTION")
        obj.addProperty("App::PropertyString", "PartID").PartID = pid
        obj.addProperty("App::PropertyBool", "TestOnly").TestOnly = spec.get("test_only", False)
        obj.addProperty("App::PropertyFloat", "MaleDiameterCorrection").MaleDiameterCorrection = spec["male_diameter_correction"]
        obj.addProperty("App::PropertyFloat", "FemaleRadialClearance").FemaleRadialClearance = spec["female_radial_clearance"]
    library.recompute()
    lib_file = OUT / "cad" / "Type-library.FCStd"
    library.saveAs(str(lib_file))
    App.closeDocument(library.Name)
    reopened = App.openDocument(str(lib_file))
    assert len([o for o in reopened.Objects if "Shape" in o.PropertiesList and o.Shape.isValid()]) == len(shapes)
    write_json(OUT / "validation" / "native-documents.json", {
        "status": "PASS", "headless_native_reopened": True,
        "assembly_objects": len(objects), "separate_library_types": len(shapes),
        "no_extra_library_solids_in_assembly_document": True,
        "all_bounds_volumes_types_steps_color_attributes_match": True,
        "native_sha256": sha256(file), "library_sha256": sha256(lib_file),
        "gui_viewport_colors": "NOT_VERIFIED",
        "gui_limitation": "An isolated offscreen GUI startup did not return. No existing application "
            "was touched. Shapes, names, placements, step groups and PartColor attributes are saved and "
            "verified via native reopen; GUI display colors may use FreeCAD defaults.",
    })
    App.closeDocument(reopened.Name)
    print("NATIVE_DOCUMENTS_VALIDATED", len(objects), "assembly objects,", len(shapes), "library types")


if __name__ == "__main__":
    main()
