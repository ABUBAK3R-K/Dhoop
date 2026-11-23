import os
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

from app.config import settings
from dhoop.overpass import fetch_overpass_buildings
from dhoop.osm_parse import parse_osm_elements
from dhoop.heights import assign_heights
from dhoop.geometry import build_scene_meshes
from dhoop.sun import sun_series, compute_sun_windows
from dhoop.compose import compose_frames
from dhoop.video import encode_timelapse_video
from dhoop.report import compute_confidence, compute_solar_qualification, format_summary_html

tz_finder = TimezoneFinder()

def run_job_pipeline(
    job_id: str,
    lat: float,
    lon: float,
    floor: int = 0,
    facing: Optional[str] = None,
    target_date: Optional[str] = None,
    radius_m: float = 300.0,
    job_dir: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute the full end-to-end Dhoop Solar rooftop qualification pipeline."""
    if job_dir is None:
        job_dir = os.path.join(settings.JOBS_DIR, job_id)
    job_dir = os.path.abspath(job_dir)
    os.makedirs(job_dir, exist_ok=True)
    frames_raw_dir = os.path.join(job_dir, "frames_raw")
    frames_hud_dir = os.path.join(job_dir, "frames_hud")
    os.makedirs(frames_raw_dir, exist_ok=True)
    os.makedirs(frames_hud_dir, exist_ok=True)

    timing_ms: Dict[str, int] = {}
    t_start_total = time.time()

    # 1. Determine local timezone and reference dates
    tz_str = tz_finder.timezone_at(lat=lat, lng=lon) or "Asia/Kolkata"
    tz = ZoneInfo(tz_str)
    now_local = datetime.now(tz)
    local_today_str = target_date or now_local.strftime("%Y-%m-%d")
    current_year = now_local.year
    dec21_str = f"{current_year}-12-21"
    jun21_str = f"{current_year}-06-21"

    # 2. Stage: Fetch OSM
    t0 = time.time()
    raw_elements = fetch_overpass_buildings(lat=lat, lon=lon, radius_m=radius_m)
    timing_ms["fetch"] = int((time.time() - t0) * 1000)

    # 3. Stage: Parse OSM elements
    t0 = time.time()
    parsed_buildings = parse_osm_elements(raw_elements)
    timing_ms["parse"] = int((time.time() - t0) * 1000)

    # 4. Stage: Heights & Estimation
    t0 = time.time()
    buildings_with_height, height_coverage = assign_heights(
        buildings=parsed_buildings,
        pin_lat=lat,
        pin_lon=lon,
        default_height=settings.DEFAULT_BUILDING_HEIGHT_M,
        floor_height_m=settings.FLOOR_HEIGHT_M
    )
    timing_ms["heights"] = int((time.time() - t0) * 1000)

    # 5. Stage: Geometry & Rooftop Grid Discretization
    t0 = time.time()
    scene_data = build_scene_meshes(
        buildings=buildings_with_height,
        lat0=lat,
        lon0=lon,
        radius_m=radius_m,
        floor=floor,
        facing=facing,
        floor_height_m=settings.FLOOR_HEIGHT_M,
        sample_height_offset_m=settings.SAMPLE_HEIGHT_OFFSET_M,
        grid_spacing_m=1.5
    )
    timing_ms["geometry"] = int((time.time() - t0) * 1000)

    # 6. Stage: Sun series for 3 reference dates
    t0 = time.time()
    series_today = sun_series(local_today_str, lat, lon, tz_str, step_min=settings.SUN_STEP_MIN)
    series_dec = sun_series(dec21_str, lat, lon, tz_str, step_min=settings.SUN_STEP_MIN)
    series_jun = sun_series(jun21_str, lat, lon, tz_str, step_min=settings.SUN_STEP_MIN)
    timing_ms["sun"] = int((time.time() - t0) * 1000)

    # Choose render frames: every 30 min (FRAME_STEP_MIN) when sun is up
    step_ratio = settings.FRAME_STEP_MIN // settings.SUN_STEP_MIN
    candidate_indices = [
        i for i, s in enumerate(series_today)
        if s["el"] >= settings.MIN_SUN_ELEVATION_DEG and (i % step_ratio == 0)
    ]
    if len(candidate_indices) > settings.MAX_FRAMES:
        candidate_indices = candidate_indices[:settings.MAX_FRAMES]

    # 7. Stage: Blender subprocess (multi-point raycasting + render frames)
    stage_in = {
        "rooftop_grid": scene_data["rooftop_grid"],
        "min_el": settings.MIN_SUN_ELEVATION_DEG,
        "view_radius_m": settings.VIEW_RADIUS_M,
        "meshes": scene_data["meshes"],
        "days": [
            {"label": "today", "samples": series_today},
            {"label": "dec21", "samples": series_dec},
            {"label": "jun21", "samples": series_jun}
        ],
        "render": {
            "day_label": "today",
            "sample_indices": candidate_indices,
            "size": settings.RENDER_SIZE,
            "samples": settings.RENDER_SAMPLES,
            "out_dir": frames_raw_dir
        }
    }

    in_json_path = os.path.join(job_dir, "stage_in.json")
    out_json_path = os.path.join(job_dir, "stage_out.json")
    with open(in_json_path, "w", encoding="utf-8") as f:
        json.dump(stage_in, f)

    t0 = time.time()
    worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = dict(os.environ)
    curr_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{worker_dir}{os.pathsep}{curr_pp}" if curr_pp else worker_dir

    subprocess.run(
        [sys.executable, "-m", "dhoop.blender_stage", in_json_path, out_json_path],
        timeout=settings.BLENDER_STAGE_TIMEOUT_S,
        check=True,
        cwd=worker_dir,
        env=env
    )
    with open(out_json_path, "r", encoding="utf-8") as f:
        stage_out = json.load(f)
    timing_ms["blender"] = int((time.time() - t0) * 1000)

    # Compute sun windows & hours for each day
    days_summary = []
    days_res_map = {d["label"]: d for d in stage_out.get("days", [])}

    for label, s_date, series in [
        ("today", local_today_str, series_today),
        ("dec21", dec21_str, series_dec),
        ("jun21", jun21_str, series_jun)
    ]:
        d_entry = days_res_map.get(label, {})
        sunlit_flags = d_entry.get("sunlit", [])
        hours, windows = compute_sun_windows(
            samples=series,
            sunlit_flags=sunlit_flags,
            max_gap_merge_min=10,
            step_min=settings.SUN_STEP_MIN
        )
        days_summary.append({
            "label": label,
            "date": s_date,
            "sun_hours": hours,
            "windows": windows
        })

    # Solar qualification metrics
    dec_entry = days_res_map.get("dec21", {})
    cell_winter_hours = dec_entry.get("cell_hours", [])
    today_hours_val = next((d["sun_hours"] for d in days_summary if d["label"] == "today"), 4.0)
    jun_hours_val = next((d["sun_hours"] for d in days_summary if d["label"] == "jun21"), 6.0)

    solar_qualification = compute_solar_qualification(
        roof_area_m2=scene_data["roof_area_m2"],
        cell_winter_hours=cell_winter_hours,
        today_hours_avg=today_hours_val,
        jun_hours_avg=jun_hours_val,
        winter_threshold_hours=4.0
    )

    # 8. Stage: Compose HUD and day strip
    t0 = time.time()
    frame_samples = [series_today[idx] for idx in candidate_indices]
    composed_pngs = compose_frames(
        raw_frames_dir=frames_raw_dir,
        out_dir=frames_hud_dir,
        frame_samples=frame_samples,
        frame_sunlit=stage_out.get("frame_sunlit", []),
        solar_info=solar_qualification
    )
    timing_ms["compose"] = int((time.time() - t0) * 1000)

    # 9. Stage: Encode Video with ffmpeg
    t0 = time.time()
    mp4_path = os.path.join(job_dir, "timelapse.mp4")
    try:
        encode_timelapse_video(
            frames_dir=frames_hud_dir,
            output_mp4=mp4_path,
            fps=settings.RENDER_FPS,
            timeout_s=30
        )
        video_artifact = "timelapse.mp4"
    except Exception:
        video_artifact = None
    timing_ms["ffmpeg"] = int((time.time() - t0) * 1000)

    timing_ms["total"] = int((time.time() - t_start_total) * 1000)

    # 10. Assemble final report document
    host_b = scene_data.get("host_building")
    confidence = compute_confidence(
        explicit_share=height_coverage["explicit"],
        buildings_loaded=scene_data["buildings_loaded"],
        host_building_known=(host_b is not None)
    )

    result_doc = {
        "job_id": job_id,
        "status": "done",
        "cached": False,
        "site": {
            "host_building": {
                "osm_id": host_b["osm_id"] if host_b else None,
                "height_m": host_b.get("height_m") if host_b else None,
                "height_source": host_b.get("height_source") if host_b else None
            } if host_b else None,
            "buildings_loaded": scene_data["buildings_loaded"],
            "height_coverage": height_coverage,
            "open_spot": (host_b is None)
        },
        "solar": solar_qualification,
        "days": days_summary,
        "confidence": confidence,
        "warnings": [
            "Macro building shadows simulated from OpenStreetMap.",
            "Rooftop water tanks, parapets, stair-heads, and trees require final on-site physical survey."
        ],
        "artifacts": {
            "video": video_artifact,
            "result": "result.json"
        },
        "timing_ms": timing_ms,
        "meta": meta or {}
    }

    # Write result.json
    res_path = os.path.join(job_dir, "result.json")
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(result_doc, f, indent=2)

    return result_doc
