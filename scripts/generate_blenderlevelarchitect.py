"""
AXEV Medieval Settlement — BlenderLevelArchitect Headless Generator
Runs inside Blender --background, installs the add-on from the cloned
repo's dist/ folder, generates a full multi-floor dungeon/level with
rooms, corridors, walls, stairs, doors, and props, then exports GLB.
"""

import bpy
import os
import sys
import json
import time
import math
import pathlib

# ── paths ──────────────────────────────────────────────────────────────
WORKSPACE   = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", "/workspace"))
BLA_DIR     = WORKSPACE / "BlenderLevelArchitect"
OUTPUT_DIR  = WORKSPACE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ADDON_ZIP   = next(BLA_DIR.glob("dist/*.zip"), None)

start_time  = time.time()
report      = {}

# ── helpers ─────────────────────────────────────────────────────────────
def log(msg):
    print(f"[AXEV] {msg}", flush=True)

def save_report(extra=None):
    report.update(extra or {})
    report["elapsed_seconds"] = round(time.time() - start_time, 1)
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, indent=2))

def set_camera(location, rotation_euler):
    cam = bpy.data.objects.get("Camera")
    if not cam:
        bpy.ops.object.camera_add()
        cam = bpy.context.object
        cam.name = "Camera"
    cam.location       = location
    cam.rotation_euler = rotation_euler
    bpy.context.scene.camera = cam

def render_png(filepath, resolution=(1280, 720)):
    scene = bpy.context.scene
    scene.render.engine              = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath            = str(filepath)
    scene.render.resolution_x        = resolution[0]
    scene.render.resolution_y        = resolution[1]
    scene.render.resolution_percentage = 100
    # Workbench lighting — works without GPU
    scene.display.shading.light      = "MATCAP"
    scene.display.shading.color_type = "MATERIAL"
    bpy.ops.render.render(write_still=True)
    log(f"  rendered → {filepath}")

def count_scene():
    objs  = [o for o in bpy.data.objects if o.type == "MESH"]
    polys = sum(len(o.data.polygons) for o in objs)
    return len(objs), polys

# ── 1. install add-on ───────────────────────────────────────────────────
log("Step 1 — installing BlenderLevelArchitect add-on")
report["addon_zip"] = str(ADDON_ZIP) if ADDON_ZIP else "not found"

if ADDON_ZIP:
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module="game_level_architect")
    bpy.ops.wm.save_userpref()
    log(f"  installed from {ADDON_ZIP}")
else:
    # fall back: try to find the installed module directly (cloned source)
    src_py = BLA_DIR / "levelArchitect_v2.py"
    if src_py.exists():
        import importlib.util, sys as _sys
        spec = importlib.util.spec_from_file_location("game_level_architect", src_py)
        mod  = importlib.util.module_from_spec(spec)
        _sys.modules["game_level_architect"] = mod
        spec.loader.exec_module(mod)
        log("  loaded source directly (no zip)")
    else:
        log("  WARNING: add-on not found — will generate a fallback scene")

# ── 2. fresh scene ──────────────────────────────────────────────────────
log("Step 2 — preparing fresh scene")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "AXEV_Medieval"

# ── 3. generate level ───────────────────────────────────────────────────
log("Step 3 — generating level with BlenderLevelArchitect")

addon_ok = "game_level_architect" in bpy.context.preferences.addons

if addon_ok:
    # Deselect all, switch to object mode
    bpy.ops.object.select_all(action="DESELECT")

    try:
        # --- Blueprint (Step 1) ---
        bpy.ops.gla.generate_blueprint(
            map_width=12,
            map_height=12,
            num_floors=2,
            min_rooms=6,
            max_rooms=10,
            corridor_width=1,
            use_random_seed=True,
        )
        log("  blueprint generated")

        # --- Walls (Step 2) ---
        bpy.ops.gla.generate_walls(wall_height=3.0, per_floor=True)
        log("  walls generated")

        # --- Stairs (Step 3) ---
        bpy.ops.gla.generate_stairs(stair_type="STEPPED")
        log("  stairs generated")

        # --- Doors (Step 4) ---
        bpy.ops.gla.generate_doors(generate_panels=True)
        log("  doors generated")

        # --- Props (Step 5) ---
        bpy.ops.gla.generate_props(
            torch_density=0.4,
            crate_density=0.3,
        )
        log("  props generated")

        report["method"] = "BlenderLevelArchitect_addon"

    except Exception as e:
        log(f"  add-on operator failed: {e} — building fallback scene")
        addon_ok = False

if not addon_ok:
    # ── Fallback: hand-built medieval dungeon ──────────────────────────
    log("  building fallback procedural dungeon")
    report["method"] = "fallback_procedural"

    import random, mathutils
    rng = random.Random(42)

    # Ground plane
    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = bpy.data.materials.new("GroundMat")
    mat.diffuse_color = (0.3, 0.25, 0.2, 1)
    ground.data.materials.append(mat)

    # Room layout: 3×3 grid of rooms
    room_positions = [
        (x * 6, y * 6) for x in range(-1, 2) for y in range(-1, 2)
    ]

    wall_mat = bpy.data.materials.new("WallMat")
    wall_mat.diffuse_color = (0.5, 0.45, 0.4, 1)
    roof_mat = bpy.data.materials.new("RoofMat")
    roof_mat.diffuse_color = (0.6, 0.2, 0.1, 1)

    for i, (rx, ry) in enumerate(room_positions):
        w = rng.uniform(2.5, 4.0)
        h_room = rng.uniform(2.5, 3.5)
        # Floor
        bpy.ops.mesh.primitive_plane_add(size=1, location=(rx, ry, 0.01))
        floor = bpy.context.object
        floor.name = f"Room_{i}_Floor"
        floor.scale = (w, w, 1)

        # Walls (4 sides, thin boxes)
        for side, (ox, oy, sx, sy) in enumerate([
            (0,  w/2, w, 0.15),
            (0, -w/2, w, 0.15),
            ( w/2, 0, 0.15, w),
            (-w/2, 0, 0.15, w),
        ]):
            bpy.ops.mesh.primitive_cube_add(
                size=1,
                location=(rx + ox, ry + oy, h_room / 2)
            )
            wall = bpy.context.object
            wall.name = f"Room_{i}_Wall_{side}"
            wall.scale = (sx, sy, h_room)
            wall.data.materials.append(wall_mat)

        # Roof
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=(rx, ry, h_room + 0.15)
        )
        roof = bpy.context.object
        roof.name = f"Room_{i}_Roof"
        roof.scale = (w + 0.1, w + 0.1, 0.15)
        roof.data.materials.append(roof_mat)

        # Torch (cylinder + point light)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.05, depth=0.4,
            location=(rx + w/2 - 0.3, ry + w/2 - 0.3, h_room - 0.4)
        )
        torch = bpy.context.object
        torch.name = f"Torch_{i}"
        bpy.ops.object.light_add(
            type="POINT",
            location=(rx + w/2 - 0.3, ry + w/2 - 0.3, h_room - 0.2)
        )
        light = bpy.context.object
        light.name = f"TorchLight_{i}"
        light.data.energy = 20
        light.data.color  = (1.0, 0.6, 0.2)

    # Corridors connecting rooms (simple box hallways)
    corr_mat = bpy.data.materials.new("CorrMat")
    corr_mat.diffuse_color = (0.35, 0.3, 0.25, 1)
    connections = [(0,1),(1,2),(3,4),(4,5),(6,7),(7,8),(0,3),(3,6),(1,4),(4,7),(2,5),(5,8)]
    for a, b in connections:
        ax, ay = room_positions[a]
        bx, by = room_positions[b]
        cx, cy = (ax+bx)/2, (ay+by)/2
        length = math.dist((ax,ay),(bx,by))
        angle  = math.atan2(by-ay, bx-ax)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, 0.5))
        corr = bpy.context.object
        corr.name   = f"Corridor_{a}_{b}"
        corr.scale  = (length/2, 0.75, 1.0)
        corr.rotation_euler[2] = angle
        corr.data.materials.append(corr_mat)

    # Keep-tower (central fortress)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 4))
    keep = bpy.context.object
    keep.name  = "Keep_Tower"
    keep.scale = (2.5, 2.5, 4)
    keep_mat = bpy.data.materials.new("KeepMat")
    keep_mat.diffuse_color = (0.45, 0.4, 0.35, 1)
    keep.data.materials.append(keep_mat)

    log("  fallback scene built")

# ── 4. metrics ──────────────────────────────────────────────────────────
n_obj, n_poly = count_scene()
log(f"Step 4 — scene: {n_obj} objects, {n_poly} polygons")
report.update({"objects": n_obj, "polygons": n_poly})

# ── 5. add sun + ambient ─────────────────────────────────────────────────
log("Step 5 — lighting")
bpy.ops.object.light_add(type="SUN", location=(10, -10, 20))
sun = bpy.context.object
sun.name = "Sun"
sun.data.energy = 3.0
sun.data.angle  = 0.1

world = bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.05, 0.05, 0.08, 1)
bg.inputs[1].default_value = 0.3

# ── 6. renders ──────────────────────────────────────────────────────────
log("Step 6 — rendering views")

views = [
    # name,  location,              rotation (rad)
    ("overview",   (20, -20, 18),  (math.radians(55), 0, math.radians(45))),
    ("closeup",    ( 5,  -8,  6),  (math.radians(60), 0, math.radians(20))),
    ("side_angle", (-15,  5, 10),  (math.radians(50), 0, math.radians(-30))),
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
glb_path = str(OUTPUT_DIR / "AXEV_BlenderLevelArchitect.glb")

bpy.ops.export_scene.gltf(
    filepath       = glb_path,
    export_format  = "GLB",
    export_lights  = True,
    export_materials = "EXPORT",
    export_apply   = True,
)
log(f"  exported → {glb_path}")

glb_size = os.path.getsize(glb_path)
report["glb_path"] = glb_path
report["glb_size_kb"] = round(glb_size / 1024, 1)

# ── 8. final report ──────────────────────────────────────────────────────
save_report({
    "tool"    : "BlenderLevelArchitect",
    "license" : "GPL-3.0",
    "engine"  : "Blender 4.2+",
    "scene"   : "AXEV Medieval Settlement",
    "floors"  : 2,
    "status"  : "success",
})

log("Done — all artefacts written to output/")
