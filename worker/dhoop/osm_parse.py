from typing import List, Dict, Any, Optional
import shapely
from shapely.geometry import Polygon, LineString
from shapely.ops import linemerge, polygonize, unary_union

def parse_osm_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse Overpass OSM elements into building polygons with tags and IDs.
    Handles both ways and multipolygon relations."""
    buildings: List[Dict[str, Any]] = []

    for el in elements:
        el_type = el.get("type")
        tags = el.get("tags", {})
        
        # Check building tag
        building_val = tags.get("building")
        if not building_val or building_val == "no":
            continue
            
        osm_id = f"{el_type}/{el.get('id')}"

        if el_type == "way":
            geom = el.get("geometry", [])
            if len(geom) < 3:
                continue
            
            coords = [(pt["lon"], pt["lat"]) for pt in geom]
            # Ensure closed ring
            if coords[0] != coords[-1]:
                coords.append(coords[0])
                
            try:
                poly = Polygon(coords)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_empty:
                    continue
                # Area in degrees squared: area < 4 m^2 is approx area < 4 / (111000^2) ~ 3.2e-10
                if poly.area < 3e-10:
                    continue
                    
                buildings.append({
                    "osm_id": osm_id,
                    "polygon": poly,
                    "tags": tags
                })
            except Exception:
                continue

        elif el_type == "relation":
            # Multipolygon relation
            members = el.get("members", [])
            outer_lines: List[LineString] = []
            inner_lines: List[LineString] = []
            
            for m in members:
                role = m.get("role")
                m_geom = m.get("geometry", [])
                if len(m_geom) < 2:
                    continue
                line_coords = [(pt["lon"], pt["lat"]) for pt in m_geom]
                try:
                    ls = LineString(line_coords)
                    if ls.is_valid and not ls.is_empty:
                        if role == "inner":
                            inner_lines.append(ls)
                        else:
                            # Default or role == 'outer'
                            outer_lines.append(ls)
                except Exception:
                    continue

            if not outer_lines:
                continue

            try:
                # Merge outer lines and polygonize
                merged_outer = linemerge(outer_lines)
                outer_polys = list(polygonize(merged_outer))
                if not outer_polys:
                    continue
                outer_shape = unary_union(outer_polys)
                
                # If inner lines exist, merge and subtract
                if inner_lines:
                    merged_inner = linemerge(inner_lines)
                    inner_polys = list(polygonize(merged_inner))
                    if inner_polys:
                        inner_shape = unary_union(inner_polys)
                        outer_shape = outer_shape.difference(inner_shape)

                # Collect result polygons
                if isinstance(outer_shape, Polygon):
                    final_polys = [outer_shape]
                elif hasattr(outer_shape, "geoms"):
                    final_polys = [p for p in outer_shape.geoms if isinstance(p, Polygon)]
                else:
                    final_polys = []

                for poly in final_polys:
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    if poly.is_empty or poly.area < 3e-10:
                        continue
                    buildings.append({
                        "osm_id": osm_id,
                        "polygon": poly,
                        "tags": tags
                    })
            except Exception:
                continue

    return buildings
