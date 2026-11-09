"""
AXEV Medieval Settlement — Infinigen Exterior Headless Generator
Generates a procedural outdoor terrain with vegetation, rocks, water
and medieval-compatible ground using Princeton's Infinigen framework.
Runs inside Blender --background via Infinigen's Python API.
"""

import bpy
import os
import sys
import json
import time
import math
import pathlib

WORKSPACE  = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", "/workspace"))
OUTPUT_DIR = WORKSPACE / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

start_time = time.time()
report     = {}

def log(msg):
    print(f"[AXEV-INFINIGEN] {msg}", flush=True)

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
    scene.display.shading.light      = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    bpy.ops.render.render(write_still=True)
    log(f"  rendered → {filepath}")

def count_scene():
    objs  = [o for o in bpy.data.objects if o.type == "MESH"]
    polys = sum(len(o.data.polygons) for o in objs)
    return len(objs), polys

# ── 1. try Infinigen ────────────────────────────────────────────────────
log("Step 1 — checking Infinigen availability")
INFINIGEN_DIR = WORKSPACE / "infinigen"
infinigen_ok  = False

try:
    sys.path.insert(0, str(INFINIGEN_DIR))
    import infinigen  # noqa: F401
    infinigen_ok = True
    log("  Infinigen imported successfully")
except Exception as e:
    log(f"  Infinigen not available: {e}")

# ── 2. fresh scene ──────────────────────────────────────────────────────
log("Step 2 — preparing scene")
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "AXEV_Exterior"

# ── 3. generate terrain ─────────────────────────────────────────────────
log("Step 3 — generating terrain")

if infinigen_ok:
    try:
        from infinigen.assets.terrain import Terrain
        terrain = Terrain(seed=42, surface_registry=None)
        terrain.generate()
        report["method"] = "infinigen_terrain"
        log("  Infinigen terrain generated")
    except Exception as e:
        log(f"  Infinigen terrain failed: {e}")
        infinigen_ok = False

if not infinigen_ok:
    log("  building procedural terrain manually")
    report["method"] = "procedural_terrain"

    import random
    import bmesh as bm_module

    rng = random.Random(42)

    # ── Ground with subdivision ──────────────────────────────────────
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=40,
        y_subdivisions=40,
        size=60,
        location=(0, 0, 0)
    )
    terrain_obj = bpy.context.object
    terrain_obj.name = "Terrain"

    # Displace vertices to create hills
    bm = bm_module.new()
    bm.from_mesh(terrain_obj.data)
    for vert in bm.verts:
        x, y = vert.co.x, vert.co.y
        height = (
            1.5 * math.sin(x * 0.3) * math.cos(y * 0.25) +
            0.8 * math.sin(x * 0.7 + 1.2) * math.sin(y * 0.6) +
            0.4 * math.cos(x * 1.1) * math.sin(y * 0.9 + 0.5) +
            rng.uniform(-0.15, 0.15)
        )
        # flatten center area (settlement zone)
        dist_center = math.sqrt(x*x + y*y)
        if dist_center < 10:
            height *= dist_center / 10
        vert.co.z = height
    bm.to_mesh(terrain_obj.data)
    bm.free()
    # NOTE: calc_normals() removed in Blender 4.x — use normals_split_custom_set instead
    terrain_obj.data.update()

    # Terrain material (grass/earth)
    mat_ground = bpy.data.materials.new("GroundMat")
    mat_ground.use_nodes = True
    bsdf = mat_ground.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.22, 0.35, 0.12, 1)
    bsdf.inputs["Roughness"].default_value  = 0.9
    terrain_obj.data.materials.append(mat_ground)

    # ── River / path ────────────────────────────────────────────────
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -15, 0.1))
    river = bpy.context.object
    river.name  = "River"
    river.scale = (2.5, 20, 0.05)
    mat_water = bpy.data.materials.new("WaterMat")
    mat_water.use_nodes = True
    bsdf_w = mat_water.node_tree.nodes["Principled BSDF"]
    bsdf_w.inputs["Base Color"].default_value  = (0.1, 0.3, 0.6, 1)
    bsdf_w.inputs["Roughness"].default_value   = 0.05
    river.data.materials.append(mat_water)

    # ── Rocks ───────────────────────────────────────────────────────
    mat_rock = bpy.data.materials.new("RockMat")
    mat_rock.use_nodes = True
    bsdf_r = mat_rock.node_tree.nodes["Principled BSDF"]
    bsdf_r.inputs["Base Color"].default_value = (0.45, 0.42, 0.38, 1)
    bsdf_r.inputs["Roughness"].default_value  = 0.85

    for i in range(18):
        rx = rng.uniform(-25, 25)
        ry = rng.uniform(-25, 25)
        rs = rng.uniform(0.3, 1.2)
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=rs, subdivisions=2, location=(rx, ry, rs * 0.3)
        )
        rock = bpy.context.object
        rock.name = f"Rock_{i}"
        rock.scale.z = rng.uniform(0.4, 0.9)
        rock.data.materials.append(mat_rock)

    # ── Trees ───────────────────────────────────────────────────────
    mat_trunk = bpy.data.materials.new("TrunkMat")
    mat_trunk.use_nodes = True
    mat_trunk.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.3, 0.18, 0.08, 1)
    mat_leaves = bpy.data.materials.new("LeavesMat")
    mat_leaves.use_nodes = True
    mat_leaves.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.4, 0.05, 1)

    tree_positions = [(rng.uniform(-28, 28), rng.uniform(-28, 28)) for _ in range(25)]
    for i, (tx, ty) in enumerate(tree_positions):
        h = rng.uniform(2.5, 5.0)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.18, depth=h, location=(tx, ty, h/2)
        )
        trunk = bpy.context.object
        trunk.name = f"Tree_{i}_Trunk"
        trunk.data.materials.append(mat_trunk)
        bpy.ops.mesh.primitive_ico_sphere_add(
            radius=rng.uniform(0.9, 1.6),
            subdivisions=2,
            location=(tx, ty, h + 0.6)
        )
        canopy = bpy.context.object
        canopy.name = f"Tree_{i}_Canopy"
        canopy.data.materials.append(mat_leaves)

    # ── Medieval settlement (center) ────────────────────────────────
    mat_stone = bpy.data.materials.new("StoneMat")
    mat_stone.use_nodes = True
    mat_stone.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.46, 0.4, 1)
    mat_roof = bpy.data.materials.new("RoofMat2")
    mat_roof.use_nodes = True
    mat_roof.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.18, 0.08, 1)

    buildings = [
        ( 0,  0, 3, 3, 4),
        ( 5,  3, 2, 2, 2.5),
        (-4,  4, 2, 2, 2.5),
        ( 4, -4, 2, 2, 2.5),
        (-5, -3, 2, 2, 2.5),
        ( 0,  6, 1.5, 1.5, 2),
        ( 6,  0, 1.5, 1.5, 2),
    ]
    for i, (bx, by, bw, bd, bh) in enumerate(buildings):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, bh/2))
        building = bpy.context.object
        building.name  = f"Building_{i}"
        building.scale = (bw, bd, bh)
        building.data.materials.append(mat_stone)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, bh + 0.5))
        roof = bpy.context.object
        roof.name  = f"Roof_{i}"
        roof.scale = (bw + 0.1, bd + 0.1, 0.5)
        roof.data.materials.append(mat_roof)

    # ── Dirt road ───────────────────────────────────────────────────
    mat_road = bpy.data.materials.new("RoadMat")
    mat_road.use_nodes = True
    mat_road.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.45, 0.35, 0.22, 1)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -8, 0.08))
    road = bpy.context.object
    road.name  = "Road_Main"
    road.scale = (1.5, 14, 0.05)
    road.data.materials.append(mat_road)

    log("  procedural exterior scene built")

# ── 4. metrics ──────────────────────────────────────────────────────────
n_obj, n_poly = count_scene()
log(f"Step 4 — scene: {n_obj} objects, {n_poly} polygons")
report.update({"objects": n_obj, "polygons": n_poly})

# ── 5. lighting ──────────────────────────────────────────────────────────
log("Step 5 — lighting")
bpy.ops.object.light_add(type="SUN", location=(20, -15, 30))
sun = bpy.context.object
sun.name = "Sun"
sun.data.energy = 4.0
sun.rotation_euler = (math.radians(45), 0, math.radians(30))

world = bpy.data.worlds.new("SkyWorld")
bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.4, 0.6, 0.9, 1)
bg.inputs[1].default_value = 0.5

# ── 6. renders ──────────────────────────────────────────────────────────
log("Step 6 — rendering views")
views = [
    ("overview",   (35, -35, 28),  (math.radians(50), 0, math.radians(45))),
    ("closeup",    ( 8,  -12, 8),  (math.radians(55), 0, math.radians(15))),
    ("side_angle", (-25, 10, 15),  (math.radians(45), 0, math.radians(-40))),
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
glb_path = str(OUTPUT_DIR / "AXEV_Infinigen_Exterior.glb")
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
    "tool"    : "Infinigen Exterior / Procedural Terrain",
    "license" : "BSD-3-Clause",
    "engine"  : "Blender 4.2+",
    "scene"   : "AXEV Medieval Settlement — Exterior",
    "status"  : "success",
})
log("Done — all artefacts written to output/")
