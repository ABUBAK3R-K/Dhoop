import sys
import os
import json
import time
import math
from typing import List, Dict, Any, Tuple, Optional

def run_raycast(
    others_verts: List[List[float]],
    others_faces: List[List[int]],
    origins: List[List[float]],
    min_el: float,
    days: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int]:
    """Execute multi-point raycasting across all rooftop grid points.
    Uses Blender's BVHTree when bpy/mathutils is available, or trimesh RayMeshIntersector as standalone engine."""
    t0 = time.time()
    from dhoop.sun import sun_vec

    use_bvh = False
    bvh = None
    trimesh_intersector = None

    try:
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        use_bvh = True
    except ImportError:
        use_bvh = False

    if others_verts and others_faces:
        if use_bvh:
            from mathutils import Vector
            from mathutils.bvhtree import BVHTree
            bvh = BVHTree.FromPolygons([Vector(v) for v in others_verts], others_faces)
        else:
            try:
                import trimesh
                import numpy as np
                tm = trimesh.Trimesh(vertices=others_verts, faces=others_faces)
                trimesh_intersector = trimesh.ray.ray_triangle.RayMeshIntersector(tm)
            except Exception:
                trimesh_intersector = None

    n_points = len(origins)
    results = []

    for day in days:
        label = day["label"]
        samples = day.get("samples", [])
        cell_sunlit_counts = [0] * n_points
        step_min = 5
        grid_sunlit_per_sample: List[List[bool]] = []

        for s in samples:
            az = s["az"]
            el = s["el"]
            if el < min_el:
                grid_sunlit_per_sample.append([False] * n_points)
                continue

            sx, sy, sz = sun_vec(az, el)
            s_tuple = (sx, sy, sz)
            offset_s = (sx * 0.05, sy * 0.05, sz * 0.05)

            sample_flags = []
            if use_bvh and bvh is not None:
                from mathutils import Vector
                s_vec = Vector(s_tuple)
                for pt in origins:
                    ray_start = Vector((pt[0] + offset_s[0], pt[1] + offset_s[1], pt[2] + offset_s[2]))
                    hit = bvh.ray_cast(ray_start, s_vec, 2000.0)
                    is_lit = (hit[0] is None)
                    sample_flags.append(is_lit)
            elif trimesh_intersector is not None:
                ray_starts = [[pt[0] + offset_s[0], pt[1] + offset_s[1], pt[2] + offset_s[2]] for pt in origins]
                ray_dirs = [s_tuple] * n_points
                hits = trimesh_intersector.intersects_any(ray_starts, ray_dirs)
                sample_flags = [not bool(h) for h in hits]
            else:
                sample_flags = [True] * n_points

            for pt_idx, flag in enumerate(sample_flags):
                if flag:
                    cell_sunlit_counts[pt_idx] += 1
            grid_sunlit_per_sample.append(sample_flags)

        cell_hours = [round(count * step_min / 60.0, 2) for count in cell_sunlit_counts]
        building_sunlit = [
            (sum(1 for f in flags if f) >= max(n_points // 2, 1))
            for flags in grid_sunlit_per_sample
        ]

        results.append({
            "label": label,
            "sunlit": building_sunlit,
            "cell_hours": cell_hours,
            "grid_sunlit": grid_sunlit_per_sample
        })

    duration_ms = int((time.time() - t0) * 1000)
    return results, duration_ms

def render_fallback_25d(
    out_dir: str,
    rooftop_grid: List[List[float]],
    cell_hours: List[float],
    sample_indices: List[int],
    day_samples: List[Dict[str, Any]],
    day_sunlit: List[bool],
    render_size: int = 720
) -> Tuple[List[str], List[bool], int]:
    """Render 3D isometric solar heatmap visualization using Pillow when Blender is not in the environment."""
    t0 = time.time()
    from PIL import Image, ImageDraw
    from dhoop.sun import sun_vec

    frame_files = []
    frame_sunlit = []

    # Projection helper: ENU meters to image pixels (Center at 360, 360)
    # Isometric slant: px = cx + (x - y)*cos(30)*scale, py = cy + (x + y)*sin(30)*scale - z*scale
    cx, cy = render_size // 2, render_size // 2
    scale = 3.0

    def project(x, y, z):
        iso_x = cx + (x - y) * 0.866 * scale
        iso_y = cy + (x + y) * 0.5 * scale - z * scale * 1.2
        return (iso_x, iso_y)

    for f_idx, s_idx in enumerate(sample_indices):
        s = day_samples[s_idx]
        is_lit = day_sunlit[s_idx] if s_idx < len(day_sunlit) else False
        frame_sunlit.append(is_lit)

        img = Image.new("RGB", (render_size, render_size), (232, 227, 216)) # Ground #E8E3D8
        draw = ImageDraw.Draw(img)

        # Draw ground grid lines
        for g_offset in range(-150, 151, 30):
            p1 = project(-150, g_offset, 0)
            p2 = project(150, g_offset, 0)
            draw.line([p1, p2], fill=(218, 212, 200), width=1)
            p3 = project(g_offset, -150, 0)
            p4 = project(g_offset, 150, 0)
            draw.line([p3, p4], fill=(218, 212, 200), width=1)

        # Sun shadow vector
        sx, sy, sz = sun_vec(s["az"], s["el"])
        shadow_len = max(1.0 / max(math.tan(math.radians(max(s["el"], 5.0))), 0.1), 0.2)
        sh_dx = -sx * shadow_len * 10
        sh_dy = -sy * shadow_len * 10

        # Draw host building shadow
        if rooftop_grid:
            min_x = min(pt[0] for pt in rooftop_grid) - 5
            max_x = max(pt[0] for pt in rooftop_grid) + 5
            min_y = min(pt[1] for pt in rooftop_grid) - 5
            max_y = max(pt[1] for pt in rooftop_grid) + 5
            h_top = max(pt[2] for pt in rooftop_grid)

            sh_pts = [
                project(min_x + sh_dx, min_y + sh_dy, 0),
                project(max_x + sh_dx, min_y + sh_dy, 0),
                project(max_x + sh_dx, max_y + sh_dy, 0),
                project(min_x + sh_dx, max_y + sh_dy, 0)
            ]
            draw.polygon(sh_pts, fill=(180, 175, 165))

            # Draw host building walls
            w_base1 = project(min_x, min_y, 0)
            w_base2 = project(max_x, min_y, 0)
            w_base3 = project(max_x, max_y, 0)
            w_top1 = project(min_x, min_y, h_top)
            w_top2 = project(max_x, min_y, h_top)
            w_top3 = project(max_x, max_y, h_top)

            draw.polygon([w_base1, w_base2, w_top2, w_top1], fill=(225, 215, 200), outline=(190, 180, 165))
            draw.polygon([w_base2, w_base3, w_top3, w_top2], fill=(205, 195, 180), outline=(190, 180, 165))

        # Draw rooftop grid cells with solar heatmap colors
        for idx, pt in enumerate(rooftop_grid):
            x, y, z = pt
            h_val = cell_hours[idx] if idx < len(cell_hours) else 4.0
            if h_val >= 4.5:
                col = (46, 204, 113) # Green #2ECC71
            elif h_val >= 3.5:
                col = (241, 196, 15) # Gold #F1C40F
            else:
                col = (44, 62, 80)   # Navy #2C3E50

            d = 1.0
            cell_poly = [
                project(x - d, y - d, z),
                project(x + d, y - d, z),
                project(x + d, y + d, z),
                project(x - d, y + d, z)
            ]
            draw.polygon(cell_poly, fill=col, outline=(30, 30, 30))

        fname = f"f{f_idx:03d}.png"
        fpath = os.path.join(out_dir, fname)
        img.save(fpath)
        frame_files.append(fname)

    duration_ms = int((time.time() - t0) * 1000)
    return frame_files, frame_sunlit, duration_ms

def run_render(
    others_verts: List[List[float]],
    others_faces: List[List[int]],
    host_verts: List[List[float]],
    host_faces: List[List[int]],
    rooftop_grid: List[List[float]],
    cell_hours: List[float],
    render_config: Dict[str, Any],
    day_samples: List[Dict[str, Any]],
    day_sunlit: List[bool],
    view_radius_m: float = 180.0
) -> Tuple[List[str], List[bool], int]:
    """Renders scene with Cycles CPU if bpy is available, or Pillow 2.5D fallback engine."""
    out_dir = render_config["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    sample_indices = render_config.get("sample_indices", [])
    render_size = render_config.get("size", 720)

    try:
        import bpy
    except ImportError:
        # Fallback 2.5D renderer
        return render_fallback_25d(
            out_dir=out_dir,
            rooftop_grid=rooftop_grid,
            cell_hours=cell_hours,
            sample_indices=sample_indices,
            day_samples=day_samples,
            day_sunlit=day_sunlit,
            render_size=render_size
        )

    # Cycles rendering when bpy is present
    t0 = time.time()
    from mathutils import Vector
    from dhoop.sun import sun_vec

    render_samples = render_config.get("samples", 24)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = render_samples
    scene.cycles.use_denoising = True
    scene.cycles.seed = 7
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x = render_size
    scene.render.resolution_y = render_size
    scene.render.image_settings.file_format = 'PNG'

    COLOR_GROUND = (0.910, 0.890, 0.847)
    COLOR_BUILDING = (0.965, 0.953, 0.925)
    COLOR_HOST = (0.941, 0.875, 0.784)
    COLOR_PRIME_SOLAR = (0.180, 0.800, 0.443)
    COLOR_GOOD_SOLAR = (0.945, 0.769, 0.059)
    COLOR_SHADED_ROOF = (0.173, 0.243, 0.314)

    def create_mesh_obj(name: str, verts: list, faces: list, color: tuple):
        if not verts or not faces:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.update()
        ob = bpy.data.objects.new(name, me)
        scene.collection.objects.link(ob)
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.8
        ob.data.materials.append(mat)
        return ob

    ground_size = 4.0 * view_radius_m
    ground_verts = [
        [-ground_size, -ground_size, 0.0],
        [ ground_size, -ground_size, 0.0],
        [ ground_size,  ground_size, 0.0],
        [-ground_size,  ground_size, 0.0]
    ]
    ground_faces = [[0, 1, 2], [0, 2, 3]]
    create_mesh_obj("ground", ground_verts, ground_faces, COLOR_GROUND)

    if others_verts and others_faces:
        create_mesh_obj("others", others_verts, others_faces, COLOR_BUILDING)
    if host_verts and host_faces:
        create_mesh_obj("host", host_verts, host_faces, COLOR_HOST)

    half_cell = 0.65
    for idx, pt in enumerate(rooftop_grid):
        x, y, z = pt
        h_val = cell_hours[idx] if idx < len(cell_hours) else 4.0
        c_color = COLOR_PRIME_SOLAR if h_val >= 4.5 else (COLOR_GOOD_SOLAR if h_val >= 3.5 else COLOR_SHADED_ROOF)
        c_verts = [
            [x - half_cell, y - half_cell, z + 0.05],
            [x + half_cell, y - half_cell, z + 0.05],
            [x + half_cell, y + half_cell, z + 0.05],
            [x - half_cell, y + half_cell, z + 0.05]
        ]
        c_faces = [[0, 1, 2], [0, 2, 3]]
        create_mesh_obj(f"grid_patch_{idx}", c_verts, c_faces, c_color)

    sun_data = bpy.data.lights.new("sun", 'SUN')
    sun_data.energy = 4.0
    sun_data.angle = math.radians(0.53)
    sun_obj = bpy.data.objects.new("sun", sun_data)
    scene.collection.objects.link(sun_obj)

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    scene.world = world
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.90, 0.93, 1.0, 1.0)
    bg.inputs[1].default_value = 0.5

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 2.2 * view_radius_m
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = Vector((0.0, -1.0 * view_radius_m, 1.4 * view_radius_m))
    cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat('-Z', 'Y').to_euler()

    def aim_sun(az_deg: float, el_deg: float):
        v = Vector(sun_vec(az_deg, el_deg))
        sun_obj.rotation_euler = v.to_track_quat('Z', 'Y').to_euler()

    frame_files = []
    frame_sunlit = []

    for f_idx, sample_idx in enumerate(sample_indices):
        s = day_samples[sample_idx]
        is_lit = day_sunlit[sample_idx] if sample_idx < len(day_sunlit) else False
        frame_sunlit.append(is_lit)

        aim_sun(s["az"], s["el"])

        fname = f"f{f_idx:03d}.png"
        fpath = os.path.join(out_dir, fname)
        scene.render.filepath = fpath
        bpy.ops.render.render(write_still=True)
        frame_files.append(fname)

    duration_ms = int((time.time() - t0) * 1000)
    return frame_files, frame_sunlit, duration_ms

def main():
    if len(sys.argv) < 3:
        print("Usage: python -m dhoop.blender_stage in.json out.json")
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = sys.argv[2]

    with open(in_path, "r", encoding="utf-8") as f:
        stage_in = json.load(f)

    rooftop_grid = stage_in.get("rooftop_grid")
    if not rooftop_grid:
        single_origin = stage_in.get("origin", [0.0, 0.0, 1.2])
        rooftop_grid = [single_origin]

    min_el = stage_in.get("min_el", 5.0)
    view_radius_m = stage_in.get("view_radius_m", 180.0)
    meshes = stage_in.get("meshes", {})
    others = meshes.get("others", {"verts": [], "faces": []})
    host = meshes.get("host", {"verts": [], "faces": []})
    days = stage_in.get("days", [])
    render_config = stage_in.get("render")

    # 1. Multi-point Raycast
    days_result, raycast_ms = run_raycast(
        others_verts=others.get("verts", []),
        others_faces=others.get("faces", []),
        origins=rooftop_grid,
        min_el=min_el,
        days=days
    )

    # 2. Render
    frame_files = []
    frame_sunlit = []
    render_ms = 0
    if render_config and render_config.get("sample_indices"):
        day_label = render_config.get("day_label", "today")
        matching_day = next((d for d in days if d["label"] == day_label), None)
        matching_res = next((r for r in days_result if r["label"] == day_label), None)
        
        winter_res = next((r for r in days_result if r["label"] == "dec21"), matching_res)
        cell_hours = winter_res.get("cell_hours", []) if winter_res else []

        if matching_day and matching_res:
            frame_files, frame_sunlit, render_ms = run_render(
                others_verts=others.get("verts", []),
                others_faces=others.get("faces", []),
                host_verts=host.get("verts", []),
                host_faces=host.get("faces", []),
                rooftop_grid=rooftop_grid,
                cell_hours=cell_hours,
                render_config=render_config,
                day_samples=matching_day.get("samples", []),
                day_sunlit=matching_res.get("sunlit", []),
                view_radius_m=view_radius_m
            )

    stage_out = {
        "days": days_result,
        "frames": frame_files,
        "frame_sunlit": frame_sunlit,
        "timing_ms": {
            "raycast": raycast_ms,
            "render": render_ms
        }
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stage_out, f, indent=2)

if __name__ == "__main__":
    main()
