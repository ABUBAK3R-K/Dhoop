import pytest
import math
from shapely.geometry import Polygon
from dhoop.geometry import extrude_mesh
from dhoop.blender_stage import run_raycast
from dhoop.report import compute_solar_qualification

def create_box_mesh(min_x, max_x, min_y, max_y, height):
    """Create a 3D box mesh from a 2D rectangle."""
    poly = Polygon([(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)])
    return extrude_mesh(poly, height_m=height)

def test_analytic_wall_shadow():
    """Analytic wall test:
    10m wall with north face at Y=0.
    Sun due south (az=180°) at 30° elevation.
    Ray origin at height 1.2m, distance d north of north face (at (0, d, 1.2)):
    Shaded when d < (10 - 1.2) / tan(30°) ≈ 15.24 m.
    Sunlit when d > 15.24 m.
    Verify d = 14 -> shaded (False), d = 16.5 -> sunlit (True)."""
    wall_verts, wall_faces = create_box_mesh(-50, 50, -10, 0, 10.0)

    days_data = [
        {
            "label": "test_day",
            "samples": [{"t": "2026-11-23T12:00:00+05:30", "az": 180.0, "el": 30.0}]
        }
    ]

    # Test point at d = 14m north (inside shadow)
    res_shaded, _ = run_raycast(
        others_verts=wall_verts,
        others_faces=wall_faces,
        origins=[[0.0, 14.0, 1.2]],
        min_el=5.0,
        days=days_data
    )
    assert res_shaded[0]["grid_sunlit"][0][0] is False

    # Test point at d = 16.5m north (outside shadow)
    res_sunlit, _ = run_raycast(
        others_verts=wall_verts,
        others_faces=wall_faces,
        origins=[[0.0, 16.5, 1.2]],
        min_el=5.0,
        days=days_data
    )
    assert res_sunlit[0]["grid_sunlit"][0][0] is True

def test_solar_qualification_metrics():
    # 100 m2 roof, 10 grid cells
    # 8 cells get >= 4h winter sun, 2 get < 4h
    cell_hours = [4.5, 5.0, 4.2, 4.8, 4.1, 4.0, 4.3, 4.6, 2.0, 1.5]
    solar = compute_solar_qualification(
        roof_area_m2=100.0,
        cell_winter_hours=cell_hours,
        today_hours_avg=5.5,
        jun_hours_avg=6.5,
        winter_threshold_hours=4.0
    )

    # 8 / 10 = 80% usable -> Grade A
    assert solar["grade"] == "A"
    assert solar["usable_percentage"] == 80.0
    assert solar["usable_solar_area_m2"] == 80.0
    assert solar["suggested_kwp"] == 8.0
    assert "PM Surya Ghar" in solar["recommendation"]
