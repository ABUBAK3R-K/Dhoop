import math
from typing import List, Dict, Any, Tuple, Optional
import shapely
from shapely.geometry import Point, Polygon
import shapely.affinity
import trimesh

def to_local(lat: float, lon: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """Project (lat, lon) to local ENU meters (+X east, +Y north) relative to (lat0, lon0)."""
    x = (lon - lon0) * math.cos(math.radians(lat0)) * 111_320.0
    y = (lat - lat0) * 110_540.0
    return x, y

def to_latlon(x: float, y: float, lat0: float, lon0: float) -> Tuple[float, float]:
    """Inverse projection from local ENU meters to (lat, lon)."""
    lat = lat0 + y / 110_540.0
    lon = lon0 + x / (math.cos(math.radians(lat0)) * 111_320.0)
    return lat, lon

def project_polygon_to_local(poly: Polygon, lat0: float, lon0: float) -> Polygon:
    """Transform a shapely Polygon in (lon, lat) to local ENU meters (x, y)."""
    cos_lat = math.cos(math.radians(lat0))
    def transform_coords(x, y, z=None):
        local_x = (x - lon0) * cos_lat * 111_320.0
        local_y = (y - lat0) * 110_540.0
        return (local_x, local_y)
    return shapely.ops.transform(transform_coords, poly)

def detect_host_building(
    buildings: List[Dict[str, Any]],
    max_distance_m: float = 25.0
) -> Optional[Dict[str, Any]]:
    """Identify the host building containing the origin (0, 0), or nearest <= 25m.
    Expects buildings to have 'local_polygon' attribute."""
    origin = Point(0.0, 0.0)
    
    # 1. Contains check
    for b in buildings:
        if b["local_polygon"].contains(origin):
            return b

    # 2. Nearest <= 25m check
    best_b = None
    min_dist = float("inf")
    for b in buildings:
        d = b["local_polygon"].distance(origin)
        if d < min_dist:
            min_dist = d
            best_b = b

    if min_dist <= max_distance_m:
        return best_b
    return None

def generate_rooftop_grid(
    poly: Polygon,
    height_m: float,
    spacing_m: float = 1.5,
    inset_m: float = 0.5
) -> List[List[float]]:
    """Discretize the host rooftop polygon into a regular sampling grid.
    Returns list of [x, y, z] points inside the inset roof polygon."""
    safe_poly = poly.buffer(-inset_m)
    if safe_poly.is_empty or not safe_poly.is_valid:
        safe_poly = poly

    minx, miny, maxx, maxy = safe_poly.bounds
    grid_points: List[List[float]] = []
    
    x = minx + spacing_m / 2.0
    while x < maxx:
        y = miny + spacing_m / 2.0
        while y < maxy:
            pt = Point(x, y)
            if safe_poly.contains(pt):
                grid_points.append([round(x, 2), round(y, 2), round(height_m + 0.1, 2)])
            y += spacing_m
        x += spacing_m

    # Fallback to centroid if polygon is too small for grid
    if not grid_points:
        c = poly.centroid
        grid_points.append([round(c.x, 2), round(c.y, 2), round(height_m + 0.1, 2)])

    return grid_points

def extrude_mesh(poly: Polygon, height_m: float) -> Tuple[List[List[float]], List[List[int]]]:
    """Extrude a 2D shapely Polygon in local coords to a 3D trimesh mesh."""
    if height_m <= 0.1:
        height_m = 0.5
    try:
        mesh = trimesh.creation.extrude_polygon(poly, height=height_m, engine="earcut")
        verts = mesh.vertices.tolist()
        faces = mesh.faces.tolist()
        return verts, faces
    except Exception:
        minx, miny, maxx, maxy = poly.bounds
        box = trimesh.creation.box(extents=[maxx - minx, maxy - miny, height_m])
        box.apply_translation([(minx + maxx) / 2.0, (miny + maxy) / 2.0, height_m / 2.0])
        return box.vertices.tolist(), box.faces.tolist()

def build_scene_meshes(
    buildings: List[Dict[str, Any]],
    lat0: float,
    lon0: float,
    radius_m: float = 300.0,
    floor: int = 0,
    facing: Optional[str] = None,
    floor_height_m: float = 3.0,
    sample_height_offset_m: float = 1.2,
    grid_spacing_m: float = 1.5
) -> Dict[str, Any]:
    """Convert buildings to local coordinates, detect host, extrude meshes,
    and generate rooftop solar grid points across the host roof."""
    disc = Point(0.0, 0.0).buffer(radius_m)
    
    processed = []
    for b in buildings:
        local_poly = project_polygon_to_local(b["polygon"], lat0, lon0)
        if not local_poly.is_valid:
            local_poly = local_poly.buffer(0)
        if local_poly.is_empty:
            continue
        if local_poly.intersects(disc):
            b_copy = dict(b)
            b_copy["local_polygon"] = local_poly
            processed.append(b_copy)

    # Detect host building
    host_building = detect_host_building(processed, max_distance_m=25.0)
    host_osm_id = host_building["osm_id"] if host_building else None

    # Separate host and occluders
    others_verts: List[List[float]] = []
    others_faces: List[List[int]] = []
    host_verts: List[List[float]] = []
    host_faces: List[List[int]] = []

    for b in processed:
        h = b.get("height_m", 9.0)
        v, f = extrude_mesh(b["local_polygon"], h)
        
        if host_osm_id and b["osm_id"] == host_osm_id:
            host_verts = v
            host_faces = f
        else:
            offset = len(others_verts)
            others_verts.extend(v)
            for face in f:
                others_faces.append([face[0] + offset, face[1] + offset, face[2] + offset])

    # Rooftop grid for Dhoop Solar
    if host_building:
        host_poly = host_building["local_polygon"]
        host_h = host_building.get("height_m", 9.0)
        roof_area_m2 = round(host_poly.area, 1)
        rooftop_grid = generate_rooftop_grid(host_poly, host_h, spacing_m=grid_spacing_m)
    else:
        # Open ground spot fallback
        sample_z = floor * floor_height_m + sample_height_offset_m
        roof_area_m2 = 50.0  # nominal
        rooftop_grid = [[0.0, 0.0, round(sample_z, 2)]]

    return {
        "host_building": host_building,
        "buildings_loaded": len(processed),
        "roof_area_m2": roof_area_m2,
        "rooftop_grid": rooftop_grid,
        "meshes": {
            "others": {"verts": others_verts, "faces": others_faces},
            "host": {"verts": host_verts, "faces": host_faces}
        }
    }
