"""Real distributed meshes; -- --preview renders the early CAD-based handoff."""
import argparse
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, BUILD, kit, read_json, sha256, write_json


def import_binary_stl(path, name):
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    assert len(data) == 84 + 50 * count, "Binary STL required"
    vertices, faces = [], []
    for index in range(count):
        values = struct.unpack_from("<12fH", data, 84 + index * 50)
        start = len(vertices)
        vertices.extend([tuple(v * .001 for v in values[j:j + 3]) for j in (3, 6, 9)])
        faces.append((start, start + 1, start + 2))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


def point_camera(camera, location, target):
    camera.location = location
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def linear_color(hex_color):
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb)


def studio_lighting(scene):
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.93, .95, .96, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    for name, position, power, size in (
        ("Key", (.32, -.35, .50), .99, .35),
        ("FaceFill", (.38, .22, .30), .66, .35),
        ("BackRim", (-.22, .12, .38), .825, .30),
    ):
        lamp = bpy.data.lights.new(name, "AREA")
        lamp.energy, lamp.shape, lamp.size = power, "DISK", size
        obj = bpy.data.objects.new(name, lamp)
        scene.collection.objects.link(obj)
        point_camera(obj, position, (.096, .064, .06))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    data, catalog = kit(), read_json(OUT / "data" / "catalog.json")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene["model_units"] = "meters; distributed STL millimeters multiplied by 0.001 exactly once"
    scene["revision"] = data["revision"]
    scene["physical_fit"] = "UNVERIFIED"
    scene.render.engine = "BLENDER_EEVEE"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.studiolight_rotate_z = 2.8
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.curvature_ridge_factor = 1.1
    scene.display.shading.curvature_valley_factor = 1.0
    scene.display.shading.show_object_outline = False
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (.82, .85, .88)
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.fps = 12
    scene.view_settings.view_transform = "Standard"
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "AssemblyCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = .265
    camera.data.clip_start = .001
    camera.data.clip_end = 10
    scene.camera = camera
    studio_lighting(scene)
    target = Vector((.096, .064, .052))
    point_camera(camera, (.36, -.36, .25), target)
    meshes, materials = {}, {}
    for color_id, color in data["colors"].items():
        mat = bpy.data.materials.new(color_id)
        mat.use_nodes = True
        mat.diffuse_color = (*linear_color(color["hex"]), 1)
        shader = mat.node_tree.nodes["Principled BSDF"]
        shader.inputs["Base Color"].default_value = mat.diffuse_color
        shader.inputs["Roughness"].default_value = .42
        ao = mat.node_tree.nodes.new("ShaderNodeAmbientOcclusion")
        ao.name = "Contact shading"
        ao.inputs["Color"].default_value = mat.diffuse_color
        ao.inputs["Distance"].default_value = .004
        mat.node_tree.links.new(ao.outputs["Color"], shader.inputs["Base Color"])
        materials[color_id] = mat
    instances = []
    for inst in data["instances"]:
        pid = inst["part"]
        if pid not in meshes:
            meshes[pid] = import_binary_stl(OUT / catalog["parts"][pid]["stl"], pid)
        obj = bpy.data.objects.new(inst["id"], meshes[pid])
        scene.collection.objects.link(obj)
        obj.location = tuple(x * .001 for x in inst["translation_mm"])
        obj.rotation_euler[2] = math.radians(inst["rotation_deg"])
        color = data["colors"][inst["color"]]["hex"]
        rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        obj.color = (*rgb, 1)
        if not obj.data.materials:
            obj.data.materials.append(materials[inst["color"]])
        obj.material_slots[0].link = "OBJECT"
        obj.material_slots[0].material = materials[inst["color"]]
        obj["part_id"] = pid
        obj["color_id"] = inst["color"]
        obj["step"] = inst["step"]
        obj["stl_sha256"] = catalog["parts"][pid]["sha256"]
        obj["assembly_translation_mm"] = inst["translation_mm"]
        instances.append((inst, obj))
    scene["instance_count"] = len(instances)
    (OUT / "media").mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(OUT / "media" / "hero.png")
    bpy.ops.render.render(write_still=True)
    if args.preview:
        scene.render.filepath = "//../media/user-render-"
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "cad" / "Octodesk-r1.blend"))
        print("PREVIEW_RENDERED", scene.render.filepath)
        return
    views = {
        "front": ((.096, -.38, .065), .23),
        "right": ((.48, .064, .065), .195),
        "back": ((.096, .48, .08), .24),
        "left": ((-.35, .064, .07), .21),
        "top": ((.096, .064, .5), .23),
        "underside": ((.096, .064, -.4), .23),
    }
    for name, (location, scale) in views.items():
        point_camera(camera, location, target)
        camera.data.ortho_scale = scale
        scene.render.filepath = str(OUT / "media" / f"{name}.png")
        bpy.ops.render.render(write_still=True)
    for inst, obj in instances:
        obj.location.z += (inst["step"] - 1) * .0035
    point_camera(camera, (.45, -.43, .36), (.096, .064, .125))
    camera.data.ortho_scale = .39
    scene.render.filepath = str(OUT / "media" / "exploded.png")
    bpy.ops.render.render(write_still=True)
    for inst, obj in instances:
        obj.location = tuple(x * .001 for x in inst["translation_mm"])
    point_camera(camera, (.36, -.36, .25), target)
    camera.data.ortho_scale = .28
    frames_per_step = 12
    for inst, obj in instances:
        start = 2 + (inst["step"] - 1) * frames_per_step
        local_index = data["steps"][inst["step"] - 1]["instances"].index(inst["id"])
        size = len(data["steps"][inst["step"] - 1]["instances"])
        arrive = start + round(local_index / max(size, 1) * 4)
        final = Vector(tuple(x * .001 for x in inst["translation_mm"]))
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=1)
        obj.keyframe_insert("hide_render", frame=arrive - 1)
        obj.hide_render = False
        obj.keyframe_insert("hide_render", frame=arrive)
        obj.location = final + Vector((0, 0, .04))
        obj.keyframe_insert("location", frame=arrive)
        obj.location = final
        obj.keyframe_insert("location", frame=start + frames_per_step - 1)
        if obj.animation_data and obj.animation_data.action:
            for layer in obj.animation_data.action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        for curve in bag.fcurves:
                            for key in curve.keyframe_points:
                                key.interpolation = "CONSTANT" if "hide" in curve.data_path else "LINEAR"
    assembly_end = 1 + len(data["steps"]) * frames_per_step
    scene.frame_start, scene.frame_end = 1, assembly_end + 48
    initial_vector = camera.location - target
    for index in range(49):
        a = index / 48 * math.tau
        v = Vector((initial_vector.x * math.cos(a) - initial_vector.y * math.sin(a),
                    initial_vector.x * math.sin(a) + initial_vector.y * math.cos(a),
                    initial_vector.z))
        point_camera(camera, target + v, target)
        camera.keyframe_insert("location", frame=assembly_end + index)
        camera.keyframe_insert("rotation_euler", frame=assembly_end + index)
    scene.frame_set(assembly_end)
    scene.render.filepath = "//../media/user-render-"
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "cad" / "Octodesk-r1.blend"))
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 800, 660
    frames = BUILD / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(frames / "frame-")
    bpy.ops.render.render(animation=True)
    write_json(OUT / "validation" / "blender-generation.json", {
        "renderer": "Blender EEVEE stills; Workbench studio assembly animation", "blender": bpy.app.version_string,
        "distributed_stl": True, "mm_to_m": .001, "instances": len(instances),
        "assembly_end_frame": assembly_end, "frames": scene.frame_end, "fps": 12,
        "frame_steps": [{"start": 2 + (s["number"] - 1) * frames_per_step,
                         "end": 1 + s["number"] * frames_per_step,
                         "step": s["number"], "instances": s["instances"]} for s in data["steps"]],
        "mesh_hashes": {pid: catalog["parts"][pid]["sha256"] for pid in meshes},
    })
    print("BLENDER_COMPLETE", scene.frame_end)


if __name__ == "__main__":
    main()
