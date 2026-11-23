import pytest
from shapely.geometry import Polygon
from dhoop.heights import parse_length_to_m, parse_height_m, assign_heights

def test_parse_length_to_m():
    assert parse_length_to_m("12") == 12.0
    assert parse_length_to_m("12.5") == 12.5
    assert parse_length_to_m("12 m") == 12.0
    assert parse_length_to_m("12m") == 12.0
    assert parse_length_to_m("40'") == 12.19
    assert parse_length_to_m("40 ft") == 12.19
    assert parse_length_to_m("40feet") == 12.19
    
    # Reject semicolon-separated multiples
    assert parse_length_to_m("12;15") is None
    
    # Bogus & out-of-range values
    assert parse_length_to_m("abc") is None
    assert parse_length_to_m("") is None
    assert parse_length_to_m(None) is None
    assert parse_length_to_m("1.5") is None   # < 2.5m rejected
    assert parse_length_to_m("500") is None   # > 400m rejected

def test_parse_height_m():
    # Explicit height tag
    m, src = parse_height_m({"height": "18 m"})
    assert m == 18.0
    assert src == "height_tag"

    # Levels tag
    m, src = parse_height_m({"building:levels": "5"})
    assert m == 15.0
    assert src == "levels"

    # Levels with semicolon
    m, src = parse_height_m({"building:levels": "4;2"})
    assert m == 12.0
    assert src == "levels"

    # Bogus levels
    m, src = parse_height_m({"building:levels": "abc"})
    assert m is None
    assert src == "none"

    # Missing tags
    m, src = parse_height_m({})
    assert m is None
    assert src == "none"

def test_assign_heights_neighbor_median_and_fallback():
    # Create 6 buildings: 3 with explicit height, 2 without, 1 far away
    # Coordinates in Bengaluru (~12.97, 77.59)
    b1 = {
        "osm_id": "way/1",
        "polygon": Polygon([(77.590, 12.970), (77.591, 12.970), (77.591, 12.971), (77.590, 12.971)]),
        "tags": {"height": "10"}
    }
    b2 = {
        "osm_id": "way/2",
        "polygon": Polygon([(77.591, 12.970), (77.592, 12.970), (77.592, 12.971), (77.591, 12.971)]),
        "tags": {"height": "12"}
    }
    b3 = {
        "osm_id": "way/3",
        "polygon": Polygon([(77.592, 12.970), (77.593, 12.970), (77.593, 12.971), (77.592, 12.971)]),
        "tags": {"height": "20"}
    }
    b_unknown = {
        "osm_id": "way/4",
        "polygon": Polygon([(77.5905, 12.9705), (77.5915, 12.9705), (77.5915, 12.9715), (77.5905, 12.9715)]),
        "tags": {}
    }

    buildings = [b1, b2, b3, b_unknown]
    assigned, coverage = assign_heights(buildings, pin_lat=12.9705, pin_lon=77.5905)

    # Median of 10, 12, 20 is 12
    assert b_unknown["height_m"] == 12.0
    assert b_unknown["height_source"] == "neighbors"
    # b1, b2, and b_unknown are within 150m (2 explicit out of 3 = 0.67)
    assert coverage["explicit"] == 0.67
    assert coverage["estimated"] == 0.33

def test_assign_heights_default_fallback():
    # When no buildings have explicit height
    b = {
        "osm_id": "way/1",
        "polygon": Polygon([(77.590, 12.970), (77.591, 12.970), (77.591, 12.971), (77.590, 12.971)]),
        "tags": {}
    }
    assigned, coverage = assign_heights([b], pin_lat=12.970, pin_lon=77.590, default_height=9.0)
    assert assigned[0]["height_m"] == 9.0
    assert assigned[0]["height_source"] == "default"
    assert coverage["explicit"] == 0.0
    assert coverage["estimated"] == 1.0
