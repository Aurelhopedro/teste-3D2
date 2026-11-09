"""
AXEV Medieval Settlement — Infinigen Indoors Headless Generator
Generates a procedural medieval interior room (great hall, dungeon
chamber, or tavern) using Infinigen Indoors or a pure-Python fallback.
Runs inside Blender --background.
"""

import bpy
import os
import sys
import json
import time
import math
import pathlib
import random

WORKSPACE  = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", "/workspace"))
OUTPUT_DIR = WORKSPACE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

start_time = time.time()
report     = {}

def log(msg):
    print(f"[AXEV-INDOORS] {msg}", flush=True)

def save_report(extra=None):
    report.update(extra or {})
    report["elapsed_seconds"] = round(time.time() - start_time, 1)
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, indent=2))

def set_camera(location, rotation_euler):
    cam = bpy.data.objects.get("RenderCam")
    if not cam:
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        cam.name = "RenderCam"
    cam.location       = location
    cam.rotation_euler = rotation_euler
    bpy.context.scene.camera = cam

def render_png(filepath, resolution=(1280, 720)):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(filepath)
    scene.render.resolution_x = resolution[0]
    scene.render.resolution_y = resolution[1]
    scene.render.resolution_percentage = 100
    scene.display.shading.light      = "MATCAP"
    scene.display.shading.color_type = "MATERIAL"
    bpy.ops.render.render(write_still=True)
    log(f"  rendered → {filepath}")

def count_scene():
    objs  = [o for o in bpy.data.objects if o.type == "MESH"]
    polys = sum(len(o.data.polygons) for o in objs)
    return len(objs), polys

def make_material(name, color, roughness=0.8, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value  = roughness
    bsdf.inputs["Metallic"].default_value   = metallic
    return mat

# ── 1. try Infinigen Indoors ─────────────────────────────────────────────
log("Step 1 — checking Infinigen Indoors availability")
INFINIGEN_DIR = WORKSPACE / "infinigen"
infinigen_ok  = False

try:
    sys.path.insert(0, str(INFINIGEN_DIR))
    from infinigen.assets.indoors import room  # noqa
    infinigen_ok = True
    log("  Infinigen Indoors available")
except Exception as e:
    log(f"  Infinigen Indoors not available: {e}")

# ── 2. fresh scene ──────────────────────────────────────────────────────
log("Step 2 — preparing scene")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "AXEV_Interior"

# ── 3. generate interior ─────────────────────────────────────────────────
log("Step 3 — generating interior")

if infinigen_ok:
    try:
        from infinigen.assets.indoors import room as room_gen
        room_gen.generate(seed=42, room_type="medieval_hall")
        report["method"] = "infinigen_indoors"
        log("  Infinigen Indoors room generated")
    except Exception as e:
        log(f"  Infinigen Indoors generate failed: {e}")
        infinigen_ok = False

if not infinigen_ok:
    log("  building procedural medieval interior manually")
    report["method"] = "procedural_interior"
    rng = random.Random(42)

    # ── Room dimensions ─────────────────────────────────────────────
    RW, RD, RH = 10.0, 14.0, 4.5   # width, depth, height

    mat_stone  = make_material("StoneMat",  (0.50, 0.46, 0.40), roughness=0.9)
    mat_floor  = make_material("FloorMat",  (0.35, 0.30, 0.25), roughness=0.95)
    mat_wood   = make_material("WoodMat",   (0.38, 0.22, 0.10), roughness=0.85)
    mat_iron   = make_material("IronMat",   (0.30, 0.30, 0.32), roughness=0.6, metallic=0.8)
    mat_candle = make_material("CandleMat", (1.00, 0.85, 0.40), roughness=0.3)
    mat_banner = make_material("BannerMat", (0.60, 0.05, 0.05), roughness=0.9)

    def add_box(name, loc, scale, mat):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        obj = bpy.context.object
        obj.name  = name
        obj.scale = scale
        obj.data.materials.append(mat)
        return obj

    # Floor
    add_box("Floor", (0, 0, 0.05), (RW, RD, 0.1), mat_floor)

    # Ceiling
    add_box("Ceiling", (0, 0, RH), (RW, RD, 0.15), mat_stone)

    # Walls
    add_box("Wall_N", (0,  RD/2, RH/2), (RW,   0.3, RH), mat_stone)
    add_box("Wall_S", (0, -RD/2, RH/2), (RW,   0.3, RH), mat_stone)
    add_box("Wall_E", ( RW/2, 0, RH/2), (0.3, RD,   RH), mat_stone)
    add_box("Wall_W", (-RW/2, 0, RH/2), (0.3, RD,   RH), mat_stone)

    # Columns (4 pairs along long axis)
    col_positions = [-5, -2, 1, 4]
    for i, cy in enumerate(col_positions):
        for cx in [-3.5, 3.5]:
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.25, depth=RH, location=(cx, cy, RH/2)
            )
            col = bpy.context.object
            col.name = f"Column_{i}_{int(cx)}"
            col.data.materials.append(mat_stone)
            # column cap
            add_box(f"ColCap_{i}_{int(cx)}", (cx, cy, RH - 0.2), (0.6, 0.6, 0.3), mat_stone)

    # Long dining table
    add_box("Table_Top",  (0, 0, 1.0), (2.0, 7.0, 0.1), mat_wood)
    add_box("Table_Leg1", (-0.8, -3.0, 0.5), (0.15, 0.15, 1.0), mat_wood)
    add_box("Table_Leg2", ( 0.8, -3.0, 0.5), (0.15, 0.15, 1.0), mat_wood)
    add_box("Table_Leg3", (-0.8,  3.0, 0.5), (0.15, 0.15, 1.0), mat_wood)
    add_box("Table_Leg4", ( 0.8,  3.0, 0.5), (0.15, 0.15, 1.0), mat_wood)

    # Benches
    for side, bx in [("L", -1.5), ("R", 1.5)]:
        add_box(f"Bench_{side}", (bx, 0, 0.55), (0.4, 6.5, 0.1), mat_wood)
        add_box(f"BenchLeg_{side}1", (bx, -3.0, 0.3), (0.1, 0.1, 0.6), mat_wood)
        add_box(f"BenchLeg_{side}2", (bx,  3.0, 0.3), (0.1, 0.1, 0.6), mat_wood)

    # Throne / chair at head
    add_box("Throne_Seat", (0, 6.0, 0.6), (0.9, 0.5, 0.1), mat_wood)
    add_box("Throne_Back", (0, 6.3, 1.2), (0.9, 0.1, 1.2), mat_wood)
    add_box("Throne_ArmL",(-0.5, 6.0, 0.9), (0.1, 0.5, 0.1), mat_wood)
    add_box("Throne_ArmR",( 0.5, 6.0, 0.9), (0.1, 0.5, 0.1), mat_wood)

    # Fireplace (south wall)
    add_box("Fireplace_Base",  (0, -6.5, 0.6), (2.0, 0.5, 1.2), mat_stone)
    add_box("Fireplace_Left",  (-1.0, -6.5, 1.5), (0.2, 0.5, 1.5), mat_stone)
    add_box("Fireplace_Right", ( 1.0, -6.5, 1.5), (0.2, 0.5, 1.5), mat_stone)
    add_box("Fireplace_Top",   (0, -6.5, 2.4),   (2.4, 0.5, 0.2), mat_stone)
    # fire glow
    bpy.ops.object.light_add(type="POINT", location=(0, -6.4, 0.5))
    fire_light = bpy.context.object
    fire_light.name = "FireLight"
    fire_light.data.energy = 80
    fire_light.data.color  = (1.0, 0.4, 0.1)

    # Wall torches
    torch_positions = [
        (-4.6, -4), (-4.6, 0), (-4.6, 4),
        ( 4.6, -4), ( 4.6, 0), ( 4.6, 4),
    ]
    for i, (tx, ty) in enumerate(torch_positions):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=0.4, location=(tx, ty, 2.8))
        torch = bpy.context.object
        torch.name = f"Torch_{i}"
        torch.data.materials.append(mat_candle)
        bpy.ops.object.light_add(type="POINT", location=(tx, ty, 3.1))
        tl = bpy.context.object
        tl.name = f"TorchLight_{i}"
        tl.data.energy = 25
        tl.data.color  = (1.0, 0.6, 0.2)

    # Banners on columns
    for i, cy in enumerate(col_positions[:2]):
        for cx in [-3.5, 3.5]:
            add_box(f"Banner_{i}_{int(cx)}", (cx, cy, 2.8), (0.6, 0.05, 1.5), mat_banner)

    # Barrel stack (corner)
    for bi, (bsx, bsy, bsz) in enumerate([
        (-4.0, -5.5, 0.4), (-3.3, -5.5, 0.4), (-4.0, -5.5, 1.2)
    ]):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.8, location=(bsx, bsy, bsz))
        barrel = bpy.context.object
        barrel.name = f"Barrel_{bi}"
        barrel.data.materials.append(mat_wood)

    # Iron chandelier (ceiling center)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=1.2, minor_radius=0.06, location=(0, 0, 3.8)
    )
    chand = bpy.context.object
    chand.name = "Chandelier_Ring"
    chand.data.materials.append(mat_iron)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=1.0, location=(0, 0, 4.2))
    chain = bpy.context.object
    chain.name = "Chandelier_Chain"
    chain.data.materials.append(mat_iron)
    bpy.ops.object.light_add(type="POINT", location=(0, 0, 3.6))
    chand_light = bpy.context.object
    chand_light.name = "ChandelierLight"
    chand_light.data.energy = 60
    chand_light.data.color  = (1.0, 0.85, 0.6)

    # Door arch (north wall)
    add_box("Door_Left",  (-0.55, 6.85, 1.2), (0.2, 0.3, 2.4), mat_stone)
    add_box("Door_Right", ( 0.55, 6.85, 1.2), (0.2, 0.3, 2.4), mat_stone)
    add_box("Door_Arch",  (0,     6.85, 2.5), (1.4, 0.3, 0.3), mat_stone)
    add_box("Door_Panel", (0,     6.85, 1.1), (1.0, 0.08, 2.2), mat_wood)

    log("  procedural interior scene built")

# ── 4. metrics ──────────────────────────────────────────────────────────
n_obj, n_poly = count_scene()
log(f"Step 4 — scene: {n_obj} objects, {n_poly} polygons")
report.update({"objects": n_obj, "polygons": n_poly})

# ── 5. ambient lighting ──────────────────────────────────────────────────
log("Step 5 — lighting")
world = bpy.data.worlds.new("DungeonWorld")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.03, 0.03, 0.05, 1)
bg.inputs[1].default_value = 0.2

# ── 6. renders ──────────────────────────────────────────────────────────
log("Step 6 — rendering views")
views = [
    ("overview",   ( 12, -16, 10), (math.radians(55), 0, math.radians(40))),
    ("closeup",    (  3,   2,  3), (math.radians(40), 0, math.radians(10))),
    ("side_angle", (-10,   5,  5), (math.radians(50), 0, math.radians(-35))),
]
render_paths = []
for name, loc, rot in views:
    set_camera(loc, rot)
    out = OUTPUT_DIR / f"view_{name}.png"
    render_png(out)
    render_paths.append(str(out))
report["renders"] = render_paths

# ── 7. export GLB ────────────────────────────────────────────────────────
log("Step 7 — exporting GLB")
glb_path = str(OUTPUT_DIR / "AXEV_Infinigen_Indoors.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_path,
    export_format="GLB",
    export_lights=True,
    export_materials="EXPORT",
    export_apply=True,
)
glb_size = os.path.getsize(glb_path)
report["glb_path"]    = glb_path
report["glb_size_kb"] = round(glb_size / 1024, 1)
log(f"  exported → {glb_path} ({report['glb_size_kb']} KB)")

# ── 8. final report ──────────────────────────────────────────────────────
save_report({
    "tool"    : "Infinigen Indoors / Procedural Interior",
    "license" : "BSD-3-Clause",
    "engine"  : "Blender 4.2+",
    "scene"   : "AXEV Medieval Great Hall — Interior",
    "rooms"   : 1,
    "status"  : "success",
})
log("Done — all artefacts written to output/")
