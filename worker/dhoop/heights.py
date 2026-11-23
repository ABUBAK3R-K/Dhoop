import re
import statistics
from typing import Optional, Tuple, List, Dict, Any

FEET_TO_METERS = 0.3048

def parse_length_to_m(raw: str | int | float) -> Optional[float]:
    """Parse OSM length string into meters. Returns None on ambiguous/invalid values."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    
    # Reject semicolon-separated multiples (e.g. '12;15')
    if ";" in s:
        return None
    
    # Feet notation: e.g. 40', 40 ft, 40feet
    match_feet = re.match(r"^([\d.]+)\s*(?:'|ft|feet)$", s, re.IGNORECASE)
    if match_feet:
        try:
            val = float(match_feet.group(1)) * FEET_TO_METERS
            if 2.5 <= val <= 400.0:
                return round(val, 2)
            return None
        except ValueError:
            return None
    
    # Meters notation: e.g. 12, 12.5, 12 m, 12m
    match_meters = re.match(r"^([\d.]+)\s*(?:m|meters)?$", s, re.IGNORECASE)
    if match_meters:
        try:
            val = float(match_meters.group(1))
            if 2.5 <= val <= 400.0:
                return round(val, 2)
            return None
        except ValueError:
            return None
            
    return None

def parse_height_m(tags: Dict[str, Any], floor_height_m: float = 3.0) -> Tuple[Optional[float], str]:
    """Return (meters, source) where source in {'height_tag', 'levels', 'none'}."""
    raw = tags.get("height") or tags.get("building:height")
    if raw:
        m = parse_length_to_m(raw)
        if m is not None:
            return m, "height_tag"
            
    lv = tags.get("building:levels")
    if lv:
        try:
            first_part = str(lv).split(";")[0].strip()
            n = float(first_part)
            if 0 < n <= 130:
                return round(n * floor_height_m, 2), "levels"
        except (ValueError, IndexError):
            pass
            
    return None, "none"

def assign_heights(
    buildings: List[Dict[str, Any]],
    pin_lat: float,
    pin_lon: float,
    default_height: float = 9.0,
    floor_height_m: float = 3.0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Assign heights to all buildings, estimating missing heights via nearest 5 explicit neighbors.
    Also returns height_coverage statistics for buildings within 150m of pin."""
    explicit_buildings = []
    
    # First pass: parse explicit tags
    for b in buildings:
        h, source = parse_height_m(b.get("tags", {}), floor_height_m=floor_height_m)
        if source != "none" and h is not None:
            b["height_m"] = h
            b["height_source"] = source
            explicit_buildings.append(b)
        else:
            b["height_m"] = None
            b["height_source"] = "none"

    # Second pass: estimate for buildings with source == "none"
    for b in buildings:
        if b["height_source"] != "none":
            continue
            
        poly = b["polygon"]
        c_lon, c_lat = poly.centroid.x, poly.centroid.y
        
        if explicit_buildings:
            # Sort explicit buildings by Euclidean distance to this centroid
            def dist_sq(eb: Dict[str, Any]) -> float:
                eb_c = eb["polygon"].centroid
                dx = eb_c.x - c_lon
                dy = eb_c.y - c_lat
                return dx * dx + dy * dy
                
            nearest_5 = sorted(explicit_buildings, key=dist_sq)[:5]
            med_val = statistics.median([nb["height_m"] for nb in nearest_5])
            b["height_m"] = round(float(med_val), 2)
            b["height_source"] = "neighbors"
        else:
            b["height_m"] = default_height
            b["height_source"] = "default"
            
    # Compute coverage within 150m radius of pin
    # Approx 150m in degrees: 150 / 111_000 ~ 0.00135 deg
    radius_deg_sq = (150.0 / 111_000.0) ** 2
    within_150m = []
    explicit_150m = 0
    
    for b in buildings:
        poly = b["polygon"]
        c_lon, c_lat = poly.centroid.x, poly.centroid.y
        d_sq = (c_lon - pin_lon) ** 2 + (c_lat - pin_lat) ** 2
        if d_sq <= radius_deg_sq:
            within_150m.append(b)
            if b["height_source"] in ("height_tag", "levels"):
                explicit_150m += 1
                
    total_150m = len(within_150m)
    if total_150m > 0:
        explicit_share = round(explicit_150m / total_150m, 2)
        estimated_share = round(1.0 - explicit_share, 2)
    else:
        explicit_share = 0.0
        estimated_share = 1.0
        
    coverage = {
        "explicit": explicit_share,
        "estimated": estimated_share,
        "total_within_150m": total_150m
    }
    
    return buildings, coverage
