import pytest
import math
from dhoop.sun import sun_vec, facing_allows_sun, sun_series, compute_sun_windows

def test_sun_vec_axes():
    # East: az=90, el=0 -> +X=(1, 0, 0)
    x, y, z = sun_vec(90, 0)
    assert math.isclose(x, 1.0, abs_tol=1e-5)
    assert math.isclose(y, 0.0, abs_tol=1e-5)
    assert math.isclose(z, 0.0, abs_tol=1e-5)

    # South: az=180, el=0 -> -Y=(0, -1, 0)
    x, y, z = sun_vec(180, 0)
    assert math.isclose(x, 0.0, abs_tol=1e-5)
    assert math.isclose(y, -1.0, abs_tol=1e-5)
    assert math.isclose(z, 0.0, abs_tol=1e-5)

    # North: az=0, el=0 -> +Y=(0, 1, 0)
    x, y, z = sun_vec(0, 0)
    assert math.isclose(x, 0.0, abs_tol=1e-5)
    assert math.isclose(y, 1.0, abs_tol=1e-5)
    assert math.isclose(z, 0.0, abs_tol=1e-5)

    # Zenith: el=90 -> +Z=(0, 0, 1)
    x, y, z = sun_vec(0, 90)
    assert math.isclose(x, 0.0, abs_tol=1e-5)
    assert math.isclose(y, 0.0, abs_tol=1e-5)
    assert math.isclose(z, 1.0, abs_tol=1e-5)

def test_facing_allows_sun():
    # Sun due South (az=180, el=30): normal for S is (0, -1)
    # sun_h is (0, -cos(30)), dot with (0, -1) is > 0 -> True
    assert facing_allows_sun(180, 30, "S") is True
    assert facing_allows_sun(180, 30, "N") is False
    assert facing_allows_sun(180, 30, "ANY") is True
    assert facing_allows_sun(180, 30, None) is True

    # Sun due East (az=90, el=25)
    assert facing_allows_sun(90, 25, "E") is True
    assert facing_allows_sun(90, 25, "W") is False

def test_equator_noon_elevation():
    # Equator on March 20 (equinox), solar noon should have elevation > 85 deg
    series = sun_series("2026-03-20", lat=0.0, lon=0.0, tzname="UTC", step_min=5)
    max_el = max(s["el"] for s in series)
    assert max_el > 85.0

def test_sun_series_bangalore():
    # Bengaluru (lat 12.97, lon 77.59) on Nov 23
    series = sun_series("2026-11-23", lat=12.97, lon=77.59, tzname="Asia/Kolkata", step_min=5)
    assert len(series) == 288  # 24h * 12 per hour
    
    # Morning: at 07:00 (index 84), az should be East-ish (< 180)
    sample_0700 = series[84]
    assert sample_0700["az"] < 180.0

def test_compute_sun_windows_and_gap_merge():
    # 10 samples (50 min total)
    samples = [{"t": f"2026-11-23T08:{i*5:02d}:00+05:30"} for i in range(10)]
    # True, True, False (1 gap), True, True, False, False, False, True, True
    # First interval: 08:00 to 08:05, gap at 08:10 (5 min gap <= 10 min), next 08:15 to 08:20
    # Should merge into one window from 08:00 to 08:20
    # Gap at 08:25, 08:30, 08:35 (15 min > 10 min gap) -> separate window 08:40 to 08:45
    flags = [True, True, False, True, True, False, False, False, True, True]
    
    hours, windows = compute_sun_windows(samples, flags, max_gap_merge_min=10, step_min=5)
    assert hours == round(6 * 5 / 60.0, 2)  # 6 sunlit steps = 30 min = 0.5h
    assert len(windows) == 2
    assert windows[0] == ["08:00", "08:20"]
    assert windows[1] == ["08:40", "08:45"]
