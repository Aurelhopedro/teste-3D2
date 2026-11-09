"""
AXEV Urban Combat Zone — Godot Environment Generator
Generates a realistic modern urban environment (buildings, streets,
rubble, vehicles, walls) suitable for placing a soldier character.
Runs as a standard Python script (NOT inside Blender).
"""

import os
import sys
import json
import time
import math
import pathlib
import subprocess
import shutil
import random

WORKSPACE  = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", "/workspace"))
OUTPUT_DIR = WORKSPACE / "output"
GODOT_DIR  = WORKSPACE / "godot-demo-projects"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

start_time = time.time()
report     = {}

def log(msg):
    print(f"[AXEV-GODOT] {msg}", flush=True)

def save_report(extra=None):
    report.update(extra or {})
    report["elapsed_seconds"] = round(time.time() - start_time, 1)
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, indent=2))

def run(cmd, cwd=None, check=True, capture=False):
    log(f"  $ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(
        cmd, cwd=cwd, shell=isinstance(cmd, str),
        capture_output=capture, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")
    return result

# ── 1. find Godot binary ─────────────────────────────────────────────────
log("Step 1 — locating Godot")
GODOT_BIN = shutil.which("godot") or shutil.which("godot4") or shutil.which("godot-mono")
if not GODOT_BIN:
    for candidate in [
        "/opt/godot/godot",
        "/usr/local/bin/godot4",
        str(WORKSPACE / "godot" / "godot"),
    ]:
        if os.path.isfile(candidate):
            GODOT_BIN = candidate
            break
log(f"  Godot binary: {GODOT_BIN}")
report["godot_binary"] = GODOT_BIN

# ── 2. locate Blender ────────────────────────────────────────────────────
BLENDER_BIN = shutil.which("blender") or "/usr/local/bin/blender"

# ── 3. generate urban combat scene via Blender ───────────────────────────
log("Step 3 — generating urban combat environment via Blender")

BLENDER_SCRIPT = WORKSPACE / "scripts" / "_godot_blender_helper.py"
BLENDER_SCRIPT.write_text(r'''
import bpy, os, math, pathlib, json, random

OUTPUT_DIR = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", "/workspace")) / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

rng = random.Random(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "AXEV_UrbanCombat"

# ── Material factory ────────────────────────────────────────────────────
def mat(name, color, rough=0.85, metal=0.0, emit=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    bsdf  = nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value  = rough
    bsdf.inputs["Metallic"].default_value   = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    return m

def add_box(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name  = name
    o.scale = scale
    if o.data.materials:
        o.data.materials[0] = material
    else:
        o.data.materials.append(material)
    return o

def add_cyl(name, loc, radius, depth, material):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc)
    o = bpy.context.object
    o.name = name
    if o.data.materials:
        o.data.materials[0] = material
    else:
        o.data.materials.append(material)
    return o

# Materials
M_ASPHALT   = mat("Asphalt",   (0.12, 0.12, 0.12), rough=0.95)
M_SIDEWALK  = mat("Sidewalk",  (0.60, 0.58, 0.55), rough=0.92)
M_CONCRETE  = mat("Concrete",  (0.55, 0.52, 0.48), rough=0.90)
M_CONCRETE2 = mat("Concrete2", (0.48, 0.45, 0.42), rough=0.88)
M_BRICK     = mat("Brick",     (0.52, 0.28, 0.18), rough=0.93)
M_GLASS     = mat("Glass",     (0.55, 0.65, 0.70), rough=0.05, metal=0.0)
M_METAL     = mat("Metal",     (0.35, 0.35, 0.38), rough=0.4,  metal=0.9)
M_RUST      = mat("Rust",      (0.45, 0.22, 0.10), rough=0.85, metal=0.6)
M_DIRT      = mat("Dirt",      (0.28, 0.22, 0.14), rough=0.97)
M_RUBBLE    = mat("Rubble",    (0.50, 0.46, 0.40), rough=0.95)
M_WOOD      = mat("Wood",      (0.32, 0.20, 0.10), rough=0.88)
M_FENCE     = mat("Fence",     (0.30, 0.30, 0.32), rough=0.6, metal=0.8)
M_SANDBAG   = mat("Sandbag",   (0.55, 0.50, 0.32), rough=0.95)
M_SIGN      = mat("Sign",      (0.90, 0.80, 0.10), rough=0.5, emit=(1,0.8,0.05))
M_TYRE      = mat("Tyre",      (0.08, 0.08, 0.08), rough=0.98)
M_VEHICLE   = mat("Vehicle",   (0.25, 0.30, 0.22), rough=0.5, metal=0.4)
M_GREENERY  = mat("Greenery",  (0.15, 0.38, 0.10), rough=0.95)
M_BARK      = mat("Bark",      (0.22, 0.14, 0.07), rough=0.90)
M_STRIPE    = mat("Stripe",    (0.90, 0.85, 0.80), rough=0.85)

# ── Ground: main street + sidewalks ─────────────────────────────────────
# Street (Z=0)
add_box("Street_Main",   (0, 0, -0.02),  (40, 10, 0.04), M_ASPHALT)
add_box("Street_Cross",  (0, 0, -0.02),  (10, 40, 0.04), M_ASPHALT)
# Road markings
for i in range(-4, 5):
    add_box(f"RoadLine_{i}", (i*4, 0, 0.001), (1.5, 0.15, 0.001), M_STRIPE)
# Sidewalks
for sy in [6, -6]:
    add_box(f"Sidewalk_{sy}", (0, sy, 0.08), (40, 2, 0.16), M_SIDEWALK)
for sx in [6, -6]:
    add_box(f"SidewalkX_{sx}", (sx, 0, 0.08), (2, 40, 0.16), M_SIDEWALK)
# Dirt / rubble patches
for i in range(8):
    px = rng.uniform(-18, 18)
    py = rng.uniform(-18, 18)
    add_box(f"Dirt_{i}", (px, py, 0.001), (rng.uniform(0.5,2), rng.uniform(0.5,2), 0.001), M_DIRT)

# ── Buildings ────────────────────────────────────────────────────────────
buildings = [
    # name,       cx,   cy,   w,   d,  floors
    ("Bldg_A",   -14,  14,  7,  7,   5),
    ("Bldg_B",    14,  14,  9,  6,   7),
    ("Bldg_C",   -14, -14,  6,  8,   4),
    ("Bldg_D",    14, -14,  8,  7,   6),
    ("Bldg_E",   -14,   0,  5,  6,   3),
    ("Bldg_F",    14,   0,  6,  5,   5),
    ("Bldg_G",     0,  14,  5,  5,   4),
    ("Bldg_H",     0, -14,  7,  6,   3),
]

floor_h = 3.2
for bname, cx, cy, bw, bd, floors in buildings:
    h = floors * floor_h
    bm = rng.choice([M_CONCRETE, M_CONCRETE2, M_BRICK])

    # Main body
    add_box(f"{bname}_Body", (cx, cy, h/2), (bw, bd, h), bm)

    # Roof slab
    add_box(f"{bname}_Roof", (cx, cy, h + 0.1), (bw + 0.2, bd + 0.2, 0.2), M_CONCRETE)

    # Windows (grid per floor)
    win_cols = max(1, bw // 2)
    win_rows = floors
    for fi in range(int(win_rows)):
        wz = (fi + 0.5) * floor_h + 0.4
        for wi in range(int(win_cols)):
            wx_off = -bw/2 + (wi + 0.5) * (bw / win_cols)
            add_box(f"{bname}_Win_F{fi}_{wi}",
                (cx + wx_off, cy + bd/2 + 0.01, wz),
                (bw/win_cols * 0.55, 0.05, floor_h * 0.55), M_GLASS)

    # Entrance door
    add_box(f"{bname}_Door", (cx, cy - bd/2 - 0.01, 1.1),
        (1.2, 0.08, 2.2), M_METAL)

    # Damage: random rubble pile at base
    if rng.random() > 0.4:
        for ri in range(rng.randint(3, 7)):
            rx = cx + rng.uniform(-bw/2, bw/2)
            ry = cy + rng.uniform(-bd/2, bd/2)
            rs = rng.uniform(0.2, 0.7)
            add_box(f"{bname}_Rubble_{ri}", (rx, ry, rs/2),
                (rs, rs, rs), M_RUBBLE)

    # Utility box on wall
    add_box(f"{bname}_UtilBox", (cx + bw/2 + 0.1, cy, 1.2), (0.2, 0.6, 0.6), M_METAL)

# ── Street furniture ─────────────────────────────────────────────────────
# Street lamps
lamp_positions = [(-8,7),(-8,-7),(8,7),(8,-7),(0,7),(0,-7),(-16,7),(16,7)]
for i, (lx, ly) in enumerate(lamp_positions):
    add_cyl(f"LampPost_{i}", (lx, ly, 2.5), 0.05, 5.0, M_METAL)
    add_box(f"LampArm_{i}",  (lx, ly+0.4, 5.1), (0.05, 0.8, 0.05), M_METAL)
    add_box(f"LampHead_{i}", (lx, ly+0.8, 5.1), (0.3, 0.3, 0.15),
        mat(f"LampGlow_{i}", (1.0, 0.95, 0.75), rough=0.1, emit=(1.0, 0.95, 0.75)))

# Benches
for i, (bx, by) in enumerate([(-4,7),(4,7),(-4,-7),(4,-7)]):
    add_box(f"Bench_{i}_Seat", (bx, by, 0.45), (1.5, 0.4, 0.08), M_WOOD)
    for lx in [-0.6, 0.6]:
        add_box(f"Bench_{i}_Leg{lx}", (bx+lx, by, 0.22), (0.08, 0.4, 0.44), M_METAL)

# Trash bins
for i, (tx, ty) in enumerate([(-6,6),(6,6),(-6,-6),(6,-6)]):
    add_cyl(f"Bin_{i}", (tx, ty, 0.45), 0.2, 0.9, M_METAL)

# ── Military props ────────────────────────────────────────────────────────
# Sandbag barricades (3 positions)
for bi, (bax, bay, angle) in enumerate([(0, 4, 0), (-10, 0, 90), (10, 0, 90)]):
    for si in range(5):
        sx = bax + (si - 2) * 0.55
        add_box(f"SandbagLow_{bi}_{si}", (sx, bay, 0.2), (0.5, 0.35, 0.3), M_SANDBAG)
    for si in range(4):
        sx = bax + (si - 1.5) * 0.55
        add_box(f"SandbagHi_{bi}_{si}", (sx, bay, 0.5), (0.5, 0.35, 0.3), M_SANDBAG)

# Razor wire
for i in range(6):
    wx = -12 + i * 4
    add_box(f"RazorWire_{i}", (wx, 5, 0.3), (3.8, 0.1, 0.05), M_FENCE)

# Military vehicle (APC-like box shape)
add_box("APC_Body",    (-10, -3, 1.1), (4.5, 2.5, 1.4), M_VEHICLE)
add_box("APC_Turret",  (-10, -3, 2.2), (1.5, 1.5, 0.6), M_VEHICLE)
add_box("APC_Gun",     (-10, -1.5, 2.3), (0.1, 2.0, 0.1), M_METAL)
add_box("APC_Hatch",   (-10, -3, 2.55), (0.8, 0.8, 0.1), M_METAL)
for tx, ty in [(-11.5,-3.6),(-11.5,-2.4),(-8.5,-3.6),(-8.5,-2.4)]:
    add_cyl(f"APC_Wheel_{tx}", (tx, ty, 0.5), 0.5, 0.35, M_TYRE)
# Antenna
add_box("APC_Antenna", (-9.5, -4.0, 3.0), (0.04, 0.04, 1.2), M_METAL)

# Burnt-out car
add_box("Car_Body",    (10, 3, 0.65), (3.8, 1.8, 0.8), M_RUST)
add_box("Car_Cabin",   (10, 3, 1.3),  (2.0, 1.7, 0.6), M_RUST)
add_box("Car_Hood",    (11.5, 3, 0.9),(1.3, 1.7, 0.2), M_RUST)
for tx, ty in [(11.3,3.6),(11.3,2.4),(8.7,3.6),(8.7,2.4)]:
    add_cyl(f"Car_Wheel_{tx}", (tx, ty, 0.3), 0.3, 0.25, M_TYRE)

# Concrete barriers (jersey barriers)
for i in range(5):
    bx = -10 + i * 2.5
    add_box(f"Barrier_{i}", (bx, -5, 0.5), (1.0, 0.5, 1.0), M_CONCRETE)
    add_box(f"BarrierTop_{i}", (bx, -5, 1.1), (0.6, 0.4, 0.2), M_CONCRETE)

# Chain-link fence section
for fi in range(8):
    fx = -14 + fi * 4
    add_box(f"Fence_Post_{fi}", (fx, 9, 1.2), (0.08, 0.08, 2.4), M_FENCE)
    if fi < 7:
        add_box(f"Fence_Rail_{fi}", (fx+2, 9, 1.2), (3.9, 0.04, 1.8), M_FENCE)

# Dumpsters
for i, (dx, dy) in enumerate([(12,-5),(-12,5)]):
    add_box(f"Dumpster_{i}_Body", (dx, dy, 0.6), (2.5, 1.2, 1.2), M_METAL)
    add_box(f"Dumpster_{i}_Lid",  (dx, dy, 1.25),(2.6, 1.3, 0.1), M_METAL)

# Utility poles with wires
for pi, px in enumerate([-12, 0, 12]):
    add_cyl(f"UtilPole_{pi}", (px, -9, 4.0), 0.08, 8.0, M_WOOD)
    add_box(f"UtilArm_{pi}",  (px, -9, 7.8), (2.5, 0.08, 0.08), M_WOOD)
    # Wires between poles
    if pi < 2:
        mid_x = px + 6
        add_box(f"Wire_{pi}",  (mid_x, -9, 7.75), (12.0, 0.03, 0.03), M_METAL)

# Trees along sidewalk
for i, tx in enumerate([-16, -8, 0, 8, 16]):
    for ty in [7.5, -7.5]:
        h = rng.uniform(4.0, 6.0)
        add_cyl(f"Tree_Trunk_{i}_{int(ty)}", (tx, ty, h/2), 0.18, h, M_BARK)
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=rng.uniform(1.2, 1.8), subdivisions=2,
            location=(tx, ty, h + rng.uniform(0.8, 1.2)))
        crown = bpy.context.object
        crown.name = f"Tree_Crown_{i}_{int(ty)}"
        gm = rng.choice([M_GREENERY,
            mat(f"GreenVar_{i}", (0.12+rng.uniform(0,0.08),
                0.32+rng.uniform(0,0.1), 0.07), rough=0.95)])
        crown.data.materials.append(gm)

# Broken wall section
for wi in range(6):
    wh = rng.uniform(0.5, 1.8)
    add_box(f"BrokenWall_{wi}", (-5 + wi * 1.1, -11, wh/2),
        (1.0, 0.4, wh), M_BRICK)
    for ci in range(rng.randint(1, 3)):
        add_box(f"BrokenChunk_{wi}_{ci}",
            (-5 + wi*1.1 + rng.uniform(-0.5,0.5),
             -11 + rng.uniform(-0.3,0.3),
             rng.uniform(0.1,0.3)),
            (rng.uniform(0.1,0.4),)*3, M_RUBBLE)

# Barrel stack
for i, (bx, by) in enumerate([(7,-4),(7,-4.9)]):
    add_cyl(f"Barrel_{i}", (bx, by, 0.55), 0.28, 0.9, M_RUST)

# ── Lighting ─────────────────────────────────────────────────────────────
# Sun (overcast war-zone feel)
bpy.ops.object.light_add(type="SUN", location=(20, -20, 30))
sun = bpy.context.object
sun.data.energy = 2.5
sun.data.angle  = 0.05
sun.rotation_euler = (math.radians(42), 0, math.radians(30))

# Area fill light (soft sky)
bpy.ops.object.light_add(type="AREA", location=(0, 0, 25))
fill = bpy.context.object
fill.data.energy = 300
fill.data.size   = 40
fill.data.color  = (0.6, 0.65, 0.7)

# World sky
world = bpy.data.worlds.new("WarZoneSky")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.38, 0.42, 0.50, 1)
bg.inputs[1].default_value = 0.6

# ── GLB export FIRST ──────────────────────────────────────────────────────
print("[HELPER] exporting GLB...", flush=True)
bpy.ops.export_scene.gltf(
    filepath         = str(OUTPUT_DIR / "AXEV_Godot_Environment.glb"),
    export_format    = "GLB",
    export_lights    = True,
    export_materials = "EXPORT",
    export_apply     = True,
)
print("[HELPER] GLB exported", flush=True)

# ── Renders (best-effort) ─────────────────────────────────────────────────
def cam(name, loc, rot):
    bpy.ops.object.camera_add()
    c = bpy.context.object
    c.name = name
    c.location = loc
    c.rotation_euler = rot
    bpy.context.scene.camera = c

def rnd(fp):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(fp)
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.display.shading.light      = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    bpy.ops.render.render(write_still=True)

for vname, loc, rot in [
    ("overview",   (35, -35, 28), (math.radians(50), 0, math.radians(45))),
    ("street",     ( 0,  -8,  3), (math.radians(15), 0, 0)),
    ("tactical",   (-20,  0, 20), (math.radians(60), 0, math.radians(-20))),
]:
    try:
        cam(f"Cam_{vname}", loc, rot)
        rnd(OUTPUT_DIR / f"view_{vname}.png")
        print(f"[HELPER] rendered {vname}", flush=True)
    except Exception as e:
        print(f"[HELPER] render {vname} failed (non-fatal): {e}", flush=True)

# Meta
objs  = [o for o in bpy.data.objects if o.type == "MESH"]
polys = sum(len(o.data.polygons) for o in objs)
(OUTPUT_DIR / "blender_meta.json").write_text(
    __import__("json").dumps({"objects": len(objs), "polygons": polys}))
print("[HELPER] done", flush=True)
''')

run([BLENDER_BIN, "--background", "--factory-startup",
     "--python", str(BLENDER_SCRIPT), "--"])

# ── 4. generate Godot project file ──────────────────────────────────────
log("Step 4 — writing Godot project")
GODOT_SCENE_DIR = OUTPUT_DIR / "godot_project"
GODOT_SCENE_DIR.mkdir(exist_ok=True)

(GODOT_SCENE_DIR / "project.godot").write_text(
    '[gd_resource type="ProjectSettings"]\n\n'
    '[application]\n'
    'config/name="AXEV Urban Combat Zone"\n'
    'config/description="Generated by AXEV Workflow — place your soldier here"\n'
    'run/main_scene="res://main.tscn"\n'
)

glb_src = OUTPUT_DIR / "AXEV_Godot_Environment.glb"
if glb_src.exists():
    shutil.copy(glb_src, GODOT_SCENE_DIR / "AXEV_Godot_Environment.glb")

(GODOT_SCENE_DIR / "main.tscn").write_text(
    '[gd_scene load_steps=2 format=3]\n\n'
    '[ext_resource type="PackedScene" path="res://AXEV_Godot_Environment.glb" id="1"]\n\n'
    '[node name="Main" type="Node3D"]\n\n'
    '[node name="UrbanEnvironment" parent="." instance=ExtResource("1")]\n\n'
    '# Place your soldier at position (0, 0, 0.2) on the main street\n'
    '# The street runs along the X axis, buildings on both sides\n'
)

(GODOT_SCENE_DIR / "README.md").write_text(
    "# AXEV Urban Combat Zone — Godot Project\n\n"
    "## Scene contents\n"
    "- Main street intersection with asphalt + sidewalks\n"
    "- 8 multi-storey concrete/brick buildings with windows\n"
    "- Military APC vehicle + burnt-out car\n"
    "- Sandbag barricades, jersey barriers, razor wire\n"
    "- Chain-link fence, utility poles, street lamps\n"
    "- Rubble, barrels, dumpsters, benches\n"
    "- Trees along sidewalks\n\n"
    "## How to place your soldier\n"
    "1. Open Godot 4.x and import this folder\n"
    "2. Open `main.tscn`\n"
    "3. Add your soldier GLB as a child node of Main\n"
    "4. Position at `(0, 0, 0.2)` — centre of the main street\n\n"
    "## Files\n"
    "- `AXEV_Godot_Environment.glb` — full urban scene\n"
    "- `main.tscn` — Godot scene\n"
    "- `project.godot` — project settings\n"
)

# ── 5. final report ──────────────────────────────────────────────────────
meta = {}
meta_file = OUTPUT_DIR / "blender_meta.json"
if meta_file.exists():
    meta = json.loads(meta_file.read_text())

glb_size = os.path.getsize(glb_src) if glb_src.exists() else 0

save_report({
    "tool"        : "Blender 4.2 procedural",
    "scene"       : "AXEV Urban Combat Zone",
    "description" : "Modern urban environment for soldier character placement",
    "objects"     : meta.get("objects", 0),
    "polygons"    : meta.get("polygons", 0),
    "glb_size_kb" : round(glb_size / 1024, 1),
    "status"      : "success",
})
log("Done — all artefacts written to output/")
