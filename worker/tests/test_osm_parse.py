import pytest
from shapely.geometry import Polygon
from dhoop.osm_parse import parse_osm_elements

def test_parse_way_building():
    elements = [
        {
            "type": "way",
            "id": 101,
            "tags": {"building": "yes", "height": "15"},
            "geometry": [
                {"lat": 12.9710, "lon": 77.5910},
                {"lat": 12.9710, "lon": 77.5920},
                {"lat": 12.9720, "lon": 77.5920},
                {"lat": 12.9720, "lon": 77.5910},
                {"lat": 12.9710, "lon": 77.5910}
            ]
        },
        {
            # Building = no should be excluded
            "type": "way",
            "id": 102,
            "tags": {"building": "no"},
            "geometry": [
                {"lat": 12.9710, "lon": 77.5910},
                {"lat": 12.9710, "lon": 77.5920},
                {"lat": 12.9720, "lon": 77.5920},
                {"lat": 12.9710, "lon": 77.5910}
            ]
        }
    ]
    parsed = parse_osm_elements(elements)
    assert len(parsed) == 1
    assert parsed[0]["osm_id"] == "way/101"
    assert isinstance(parsed[0]["polygon"], Polygon)
    assert parsed[0]["polygon"].is_valid
    assert parsed[0]["tags"]["height"] == "15"

def test_parse_multipolygon_relation():
    # Multipolygon relation where outer boundary is split into two ways in arbitrary order
    elements = [
        {
            "type": "relation",
            "id": 201,
            "tags": {"building": "yes", "building:levels": "4"},
            "members": [
                {
                    "type": "way",
                    "ref": 301,
                    "role": "outer",
                    "geometry": [
                        {"lat": 12.970, "lon": 77.590},
                        {"lat": 12.970, "lon": 77.592},
                        {"lat": 12.972, "lon": 77.592}
                    ]
                },
                {
                    "type": "way",
                    "ref": 302,
                    "role": "outer",
                    "geometry": [
                        {"lat": 12.972, "lon": 77.592},
                        {"lat": 12.972, "lon": 77.590},
                        {"lat": 12.970, "lon": 77.590}
                    ]
                },
                {
                    # Inner ring (courtyard)
                    "type": "way",
                    "ref": 303,
                    "role": "inner",
                    "geometry": [
                        {"lat": 12.9705, "lon": 77.5905},
                        {"lat": 12.9705, "lon": 77.5915},
                        {"lat": 12.9715, "lon": 77.5915},
                        {"lat": 12.9715, "lon": 77.5905},
                        {"lat": 12.9705, "lon": 77.5905}
                    ]
                }
            ]
        }
    ]
    parsed = parse_osm_elements(elements)
    assert len(parsed) == 1
    assert parsed[0]["osm_id"] == "relation/201"
    poly = parsed[0]["polygon"]
    assert isinstance(poly, Polygon)
    assert poly.is_valid
    # Inner ring should form a hole in the polygon
    assert len(poly.interiors) == 1
