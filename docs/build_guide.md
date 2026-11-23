# Dhoop Solar — Build Guide (Milestones & Checkpoints)

Read order: `prd.md` → `design.md` → `architecture.md` → this guide.  
Target: Functional commercial rooftop solar qualifier built on **n8n + Docker + Blender Cycles CPU**.

---

## 0. The Core Solar Plan

Build the **engine first**: OSM buildings → host roof detection → rooftop grid discretization (1.5 m cells) → sun vectors (pvlib) → multi-point BVH ray-cast → shadow-free hours per cell → usable area + suggested kW + Rooftop Grade (A–D).  
Then add **Blender Cycles 3D rendering with solar heatmap overlay**.  
Then wrap in **FastAPI inside Docker**.  
Finally, orchestrate with **n8n + Telegram** to deliver instant solar lead qualification cards to installers.

---

## 1. Milestones with Checkpoints

### M0 — Skeleton & Docker Dependencies

1. Build `worker/Dockerfile` with Python 3.11, `bpy~=4.5.0`, and ffmpeg.
2. Checkpoint:

   ```bash
   docker-compose run --rm worker python -c "import bpy; print(bpy.app.version_string)"
   docker-compose run --rm worker ffmpeg -version | head -1
   ```

### M1 — OSM to Meshes & Rooftop Grid

Files: `overpass.py`, `osm_parse.py`, `heights.py`, `geometry.py`.

1. Host building polygon identification (contains pin or nearest $\le 25\text{ m}$).
2. Rooftop grid generation (`generate_rooftop_grid(poly, height, spacing_m=1.5)`).
3. Height parsing (tags → levels → 5-neighbor median → 9 m fallback).
4. Checkpoint: `pytest worker/tests -k "heights or osm_parse or geometry"` green, and script prints: roof area ($m^2$), grid points count, host building height for demo fixtures.

### M2 — Sun & Multi-Point Ray-Casting

Files: `sun.py`, `blender_stage.py`.

1. Solar series with pvlib (Today, Dec 21, Jun 21).
2. Multi-point BVH ray-casting over rooftop grid.
3. Analytic wall shadow test: 10 m wall at 30° elevation occludes points within 15.24 m.
4. Calculation of shadow-free hours per cell, usable solar area ($m^2$), suggested kW ($10\text{ m}^2 / \text{kW}$), and Rooftop Grade (A–D).
5. Checkpoint: `pytest worker/tests -k "sun or raycast"` green.

### M3 — Blender Rooftop Heatmap & MP4

Files: `blender_stage.py`, `compose.py`, `video.py`.

1. Cycles CPU 3D scene with rooftop solar heatmap (green $\ge 4.5\text{h}$, amber $3.5-4.5\text{h}$, blue shaded).
2. HUD chips showing time, Rooftop Grade, and Suggested kWp.
3. Checkpoint: full CLI pipeline generates `timelapse.mp4` and `result.json` with solar grade and usable area.

### M4 — FastAPI Service & Docker Compose

Files: `app/main.py`, `jobs.py`, `callbacks.py`, `config.py`.

1. `/v1/jobs` accepts `{lat, lon, floor}` and returns job status with `solar` metrics.
2. Checkpoint: `curl http://localhost:8000/healthz` and test job submission.

### M5 — n8n & Telegram Integration

1. Wire `dhoop-intake` (Telegram location trigger, confirmation).
2. Wire `dhoop-result` (Download MP4, send animation, format Executive Solar Qualification Card).
3. Test end-to-end with real Telegram message.

### M6 — Hardening, Offline Demo & Pitch

1. Seed `DEMO_FIXTURES=1` for offline installer demos.
2. PM Surya Ghar pitch rehearsal with rooftop qualification focus and honest limitations disclosure.
