"""Benchmark Blender Cycles render times on the current machine.
Reports seconds per frame at 720x720 and 24 samples."""

import os
import sys
import time
import json
import tempfile
import subprocess

# Add worker to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker")))

from shapely.geometry import Polygon
from dhoop.geometry import extrude_mesh

def bench():
    print("=== Dhoop Blender Render Benchmark ===")
    
    # Create sample building mesh (3 buildings)
    verts = []
    faces = []
    for i in range(3):
        poly = Polygon([(i*30, 0), (i*30 + 20, 0), (i*30 + 20, 20), (i*30, 20)])
        v, f = extrude_mesh(poly, height_m=15.0)
        offset = len(verts)
        verts.extend(v)
        for face in f:
            faces.append([face[0] + offset, face[1] + offset, face[2] + offset])

    with tempfile.TemporaryDirectory() as tmp_dir:
        stage_in = {
            "origin": [0, 0, 1.2],
            "facing": "E",
            "min_el": 5,
            "view_radius_m": 180,
            "meshes": {
                "others": {"verts": verts, "faces": faces},
                "host": {"verts": [], "faces": []}
            },
            "days": [
                {
                    "label": "today",
                    "samples": [
                        {"t": "2026-11-23T09:00:00+05:30", "az": 120.0, "el": 35.0},
                        {"t": "2026-11-23T12:00:00+05:30", "az": 180.0, "el": 55.0},
                        {"t": "2026-11-23T15:00:00+05:30", "az": 240.0, "el": 30.0}
                    ]
                }
            ],
            "render": {
                "day_label": "today",
                "sample_indices": [0, 1, 2],
                "size": 720,
                "samples": 24,
                "out_dir": os.path.join(tmp_dir, "frames")
            }
        }

        in_file = os.path.join(tmp_dir, "stage_in.json")
        out_file = os.path.join(tmp_dir, "stage_out.json")
        with open(in_file, "w", encoding="utf-8") as f:
            json.dump(stage_in, f)

        t0 = time.time()
        worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker"))
        env = dict(os.environ)
        curr_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{worker_dir}{os.pathsep}{curr_pp}" if curr_pp else worker_dir
        res = subprocess.run([sys.executable, "-m", "dhoop.blender_stage", in_file, out_file], capture_output=True, text=True, cwd=worker_dir, env=env)
        total_time = time.time() - t0

        if res.returncode != 0:
            print("Render benchmark failed:")
            print(res.stderr)
            return

        with open(out_file, "r") as f:
            out_data = json.load(f)

        timing = out_data.get("timing_ms", {})
        render_ms = timing.get("render", 0)
        n_frames = len(out_data.get("frames", []))
        sec_per_frame = (render_ms / 1000.0) / max(n_frames, 1)

        print(f"Total time: {total_time:.2f} s")
        print(f"Render time for {n_frames} frames: {render_ms/1000.0:.2f} s")
        print(f"Seconds per frame (720x720, 24 samples): {sec_per_frame:.2f} s/frame")

if __name__ == "__main__":
    bench()
