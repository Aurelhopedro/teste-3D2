"""
BPY-City build driver.
Executa o gerador original dentro do Blender, guarda .blend e exporta .glb.
"""
import argparse
import os
import sys
from pathlib import Path

import bpy


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("--output", default="output")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--grid", type=int, default=8)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    engine = Path(args.engine).resolve()
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if not (engine / "generators" / "city.py").exists():
        raise RuntimeError("Motor BPY-City não encontrado ou estrutura inesperada.")

    sys.path.insert(0, str(engine))
    from generators.city import generate_asset_city

    print("=== BPY-CITY: INÍCIO ===")
    print("Blender:", bpy.app.version_string)
    print("Seed:", args.seed)
    print("Grid:", args.grid, "x", args.grid)

    # Geração com os assets 3D originais do projeto.
    generate_asset_city(
        grid_size=(args.grid, args.grid),
        seed=args.seed,
        output_path=str(out / "BPY-City.blend"),
    )

    blend_path = out / "BPY-City.blend"
    if not blend_path.exists():
        # Compatibilidade caso a função gere a cena mas não grave o ficheiro.
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    # Exportar a cena completa para GLB, incluindo meshes e materiais.
    bpy.ops.object.select_all(action="SELECT")
    glb_path = out / "BPY-City.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_materials="EXPORT",
        export_cameras=False,
        export_lights=False,
    )

    # Render de avaliação em alta resolução com a câmara configurada pelo motor.
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if hasattr(scene, "eevee") is False else "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    if hasattr(scene, "eevee"):
        try:
            scene.eevee.taa_render_samples = 64
        except Exception:
            pass
    scene.render.filepath = str(out / "BPY-City-preview.png")
    if scene.camera:
        bpy.ops.render.render(write_still=True)
    else:
        print("AVISO: cena sem câmara; render ignorado.")

    # Relatório técnico simples para avaliar o resultado real.
    mesh_count = sum(1 for obj in bpy.data.objects if obj.type == "MESH")
    material_count = len(bpy.data.materials)
    with open(out / "BPY-City-report.txt", "w", encoding="utf-8") as f:
        f.write("BPY-City generation report\n")
        f.write(f"Blender: {bpy.app.version_string}\n")
        f.write(f"Seed: {args.seed}\n")
        f.write(f"Grid: {args.grid}x{args.grid}\n")
        f.write(f"Mesh objects: {mesh_count}\n")
        f.write(f"Materials: {material_count}\n")
        f.write(f"Blend file: {blend_path.name}\n")
        f.write(f"GLB file: {glb_path.name}\n")

    print("=== BPY-CITY: CONCLUÍDO ===")
    print("Blend:", blend_path)
    print("GLB:", glb_path)
    print("Preview:", out / "BPY-City-preview.png")


if __name__ == "__main__":
    main()
