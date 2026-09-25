import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT, kit, read_json, write_json
from blender_scene import point_camera


def main():
    data = kit()
    scene = bpy.context.scene
    generation = read_json(OUT / "validation" / "blender-generation.json")
    scene.frame_set(generation["assembly_end_frame"])
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1200, 1000
    for name, power in (("Key", .99), ("FaceFill", .66), ("BackRim", .825)):
        bpy.data.lights[name].energy = power
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.93, .95, .96, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    scene.view_settings.view_transform = "Standard"
    for material in bpy.data.materials:
        if material.use_nodes:
            nodes = material.node_tree.nodes
            shader = nodes.get("Principled BSDF")
            if shader:
                ao = nodes.get("Contact shading") or nodes.new("ShaderNodeAmbientOcclusion")
                ao.name = "Contact shading"
                ao.inputs["Color"].default_value = material.diffuse_color
                ao.inputs["Distance"].default_value = .004
                material.node_tree.links.new(ao.outputs["Color"], shader.inputs["Base Color"])
    camera = scene.camera
    target = (.096, .064, .052)
    point_camera(camera, (.36, -.36, .25), target)
    camera.data.ortho_scale = .265
    scene.render.filepath = str(OUT / "media" / "hero.png")
    bpy.ops.render.render(write_still=True)
    if "--hero-only" not in sys.argv:
        for name, location, scale in (
            ("front", (.096, -.38, .065), .23),
            ("right", (.48, .064, .065), .195),
            ("back", (.096, .48, .08), .24),
            ("left", (-.35, .064, .07), .21),
            ("top", (.096, .064, .5), .23),
            ("underside", (.096, .064, -.4), .23),
        ):
            point_camera(camera, location, target)
            camera.data.ortho_scale = scale
            scene.render.filepath = str(OUT / "media" / f"{name}.png")
            bpy.ops.render.render(write_still=True)
        for inst in data["instances"]:
            bpy.data.objects[inst["id"]].location.z += (inst["step"] - 1) * .0035
        point_camera(camera, (.45, -.43, .36), (.096, .064, .125))
        camera.data.ortho_scale = .39
        scene.render.filepath = str(OUT / "media" / "exploded.png")
        bpy.ops.render.render(write_still=True)
    scene.frame_set(generation["assembly_end_frame"] + 1)
    scene.frame_set(generation["assembly_end_frame"])
    camera.data.ortho_scale = .28
    scene.render.filepath = "//../media/user-render-"
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "cad" / "Octodesk-r1.blend"))
    write_json(OUT / "validation" / "lighting.json", {
        "revision": data["revision"], "geometry_changes": False,
        "stills_engine": "EEVEE", "color_management": "Standard; 4 mm contact shading",
        "key_watts": .99, "face_fill_watts": .66, "rim_watts": .825,
        "note": "Lighting-only correction; all mesh shapes, palette and placements unchanged.",
        "all_stills_refreshed": "--hero-only" not in sys.argv,
    })


if __name__ == "__main__":
    main()
