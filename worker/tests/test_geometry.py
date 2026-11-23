import pytest
import math
from shapely.geometry import Polygon, Point
from dhoop.geometry import (
    to_local,
    to_latlon,
    project_polygon_to_local,
    detect_host_building,
    generate_rooftop_grid,
    extrude_mesh,
    build_scene_meshes
)

def test_projection_roundtrip():
    lat0, lon0 = 12.9716, 77.5946
    dx, dy = 212.13, 212.13  # sqrt(212.13^2 + 212.13^2) ~ 300m
    lat, lon = to_latlon(dx, dy, lat0, lon0)
    x_back, y_back = to_local(lat, lon, lat0, lon0)
    
    assert math.isclose(dx, x_back, abs_tol=0.01)
    assert math.isclose(dy, y_back, abs_tol=0.01)

def test_generate_rooftop_grid():
    # 10m x 10m rooftop polygon at height 12.0m
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    grid = generate_rooftop_grid(poly, height_m=12.0, spacing_m=2.0, inset_m=0.5)
    
    # Inset polygon is 9m x 9m (from 0.5 to 9.5)
    # With 2m spacing, points should be generated inside
    assert len(grid) > 0
    for pt in grid:
        x, y, z = pt
        assert 0.5 <= x <= 9.5
        assert 0.5 <= y <= 9.5
        assert z == 12.1  # height_m + 0.1

def test_detect_host_building_contains():
    poly_inside = Polygon([(-10, -10), (10, -10), (10, 10), (-10, 10)])
    poly_other = Polygon([(50, 50), (60, 50), (60, 60), (50, 60)])
    
    buildings = [
        {"osm_id": "way/1", "local_polygon": poly_other},
        {"osm_id": "way/2", "local_polygon": poly_inside}
    ]
    host = detect_host_building(buildings, max_distance_m=25.0)
    assert host is not None
    assert host["osm_id"] == "way/2"

def test_detect_host_building_nearest_within_25m():
    poly_near = Polygon([(15, -5), (25, -5), (25, 5), (15, 5)])
    poly_far = Polygon([(50, 50), (60, 50), (60, 60), (50, 60)])
    
    buildings = [
        {"osm_id": "way/far", "local_polygon": poly_far},
        {"osm_id": "way/near", "local_polygon": poly_near}
    ]
    host = detect_host_building(buildings, max_distance_m=25.0)
    assert host is not None
    assert host["osm_id"] == "way/near"

def test_extrude_mesh_volume():
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    verts, faces = extrude_mesh(poly, height_m=5.0)
    
    assert len(verts) >= 8
    assert len(faces) >= 12
    max_z = max(v[2] for v in verts)
    min_z = min(v[2] for v in verts)
    assert math.isclose(max_z - min_z, 5.0, abs_tol=0.01)
