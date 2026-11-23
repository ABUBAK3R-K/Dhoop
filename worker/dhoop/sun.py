import math
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import pvlib

# ENU frame: +X east, +Y north, +Z up.
# Facing normals on horizontal plane (X, Y)
FACING_NORMALS: Dict[str, Optional[Tuple[float, float]]] = {
    "N": (0.0, 1.0),
    "E": (1.0, 0.0),
    "S": (0.0, -1.0),
    "W": (-1.0, 0.0),
    "ANY": None
}

def sun_vec(az_deg: float, el_deg: float) -> Tuple[float, float, float]:
    """Calculate 3D unit vector pointing towards the sun in ENU frame.
    Azimuth is degrees East of North (+X=East, +Y=North, +Z=Up)."""
    az = math.radians(az_deg)
    el = math.radians(el_deg)
    x = math.cos(el) * math.sin(az)
    y = math.cos(el) * math.cos(az)
    z = math.sin(el)
    return (x, y, z)

def facing_allows_sun(az_deg: float, el_deg: float, facing: Optional[str]) -> bool:
    """Check if the sun direction is in front of the given facade facing normal.
    sun_h · normal > 0."""
    if not facing or facing.upper() == "ANY":
        return True
    normal = FACING_NORMALS.get(facing.upper())
    if normal is None:
        return True
    sx, sy, _ = sun_vec(az_deg, el_deg)
    return (sx * normal[0] + sy * normal[1]) > 0.0

def sun_series(
    date_str: str,
    lat: float,
    lon: float,
    tzname: str,
    step_min: int = 5
) -> List[Dict[str, Any]]:
    """Compute solar azimuth and apparent elevation every step_min for the given date and local timezone."""
    times = pd.date_range(
        f"{date_str} 00:00",
        f"{date_str} 23:55",
        freq=f"{step_min}min",
        tz=tzname
    )
    sp = pvlib.solarposition.get_solarposition(times, lat, lon)
    return [
        {
            "t": t.isoformat(),
            "az": round(float(a), 2),
            "el": round(float(e), 2)
        }
        for t, a, e in zip(times, sp["azimuth"], sp["apparent_elevation"])
    ]

def compute_sun_windows(
    samples: List[Dict[str, Any]],
    sunlit_flags: List[bool],
    max_gap_merge_min: int = 10,
    step_min: int = 5
) -> Tuple[float, List[List[str]]]:
    """Calculate total sun hours and contiguous [start_time, end_time] windows formatted as HH:MM.
    Gaps <= max_gap_merge_min are bridged."""
    if not samples or not sunlit_flags or len(samples) != len(sunlit_flags):
        return 0.0, []

    total_sun_minutes = sum(1 for flag in sunlit_flags if flag) * step_min
    total_hours = round(total_sun_minutes / 60.0, 2)

    # Find raw intervals
    intervals: List[Tuple[int, int]] = []
    in_interval = False
    start_idx = 0

    for i, flag in enumerate(sunlit_flags):
        if flag and not in_interval:
            in_interval = True
            start_idx = i
        elif not flag and in_interval:
            in_interval = False
            intervals.append((start_idx, i - 1))
    if in_interval:
        intervals.append((start_idx, len(sunlit_flags) - 1))

    if not intervals:
        return total_hours, []

    # Merge intervals with small gaps
    max_gap_steps = max_gap_merge_min // step_min
    merged: List[Tuple[int, int]] = [intervals[0]]

    for cur in intervals[1:]:
        prev_start, prev_end = merged[-1]
        cur_start, cur_end = cur
        if cur_start - prev_end - 1 <= max_gap_steps:
            merged[-1] = (prev_start, cur_end)
        else:
            merged.append(cur)

    # Format as HH:MM strings
    formatted_windows = []
    for s_idx, e_idx in merged:
        t_start = samples[s_idx]["t"]
        t_end = samples[e_idx]["t"]
        # Extract HH:MM from ISO string (e.g. 2026-11-23T06:50:00+05:30 -> 06:50)
        hh_start = t_start.split("T")[1][:5]
        hh_end = t_end.split("T")[1][:5]
        formatted_windows.append([hh_start, hh_end])

    return total_hours, formatted_windows
