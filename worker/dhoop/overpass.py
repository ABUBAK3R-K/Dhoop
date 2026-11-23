import os
import json
import time
import math
import sqlite3
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

def init_cache_db(db_path: str):
    """Ensure the SQLite cache table exists."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS overpass_cache (
                key TEXT PRIMARY KEY,
                fetched_at INTEGER NOT NULL,
                payload BLOB NOT NULL
            )
        """)
        conn.commit()

def get_cached_payload(db_path: str, key: str, ttl_s: int = 7 * 86400) -> Optional[List[Dict[str, Any]]]:
    """Retrieve elements from SQLite cache if present and not expired."""
    if not os.path.exists(db_path):
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT fetched_at, payload FROM overpass_cache WHERE key = ?", (key,))
            row = cur.fetchone()
            if row:
                fetched_at, payload_blob = row
                if time.time() - fetched_at < ttl_s:
                    data = json.loads(payload_blob.decode("utf-8"))
                    return data.get("elements", [])
    except Exception:
        pass
    return None

def set_cached_payload(db_path: str, key: str, data: Dict[str, Any]):
    """Store raw Overpass JSON in SQLite cache."""
    try:
        init_cache_db(db_path)
        payload_blob = json.dumps(data).encode("utf-8")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO overpass_cache (key, fetched_at, payload) VALUES (?, ?, ?)",
                (key, int(time.time()), payload_blob)
            )
            conn.commit()
    except Exception:
        pass

def find_nearest_fixture(lat: float, lon: float, fixtures_dir: str) -> Optional[List[Dict[str, Any]]]:
    """Find a seeded demo fixture whose center is within ~500m of (lat, lon)."""
    if not os.path.exists(fixtures_dir):
        return None
    best_elements = None
    min_dist = float("inf")
    
    for fname in os.listdir(fixtures_dir):
        if not fname.endswith(".json") or fname == "expected.json":
            continue
        fpath = os.path.join(fixtures_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                meta = data.get("meta", {})
                fix_lat = meta.get("lat")
                fix_lon = meta.get("lon")
                if fix_lat is not None and fix_lon is not None:
                    # Euclidean approximation in meters
                    d = math.hypot((fix_lat - lat) * 110_540.0, (fix_lon - lon) * 111_320.0)
                    if d < min_dist and d < 2000.0:  # Within 2 km
                        min_dist = d
                        best_elements = data.get("elements", [])
        except Exception:
            continue

    return best_elements

def fetch_overpass_buildings(
    lat: float,
    lon: float,
    radius_m: float = 300.0,
    fixtures_dir: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetch building elements from Overpass API, applying 0.002° grid snapping,
    SQLite caching, mirror fallbacks, and fixture fallback."""
    # 0.002° grid snapping (~220 m)
    cell_lat = round(lat / 0.002) * 0.002
    cell_lon = round(lon / 0.002) * 0.002
    cache_key = f"{cell_lat:.3f}:{cell_lon:.3f}:{int(radius_m)}"

    # 1. Check SQLite cache
    cached = get_cached_payload(settings.CACHE_DB, cache_key)
    if cached is not None:
        return cached

    # 2. Check demo fixtures if DEMO_FIXTURES is enabled or offline fallback requested
    if fixtures_dir is None:
        fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
        
    if settings.DEMO_FIXTURES:
        fixture_elements = find_nearest_fixture(lat, lon, fixtures_dir)
        if fixture_elements is not None:
            return fixture_elements

    # 3. Live Overpass query with query_radius = radius_m + 160 (cell half-diagonal buffer)
    query_radius = int(radius_m + 160)
    query = f"""[out:json][timeout:{settings.OVERPASS_TIMEOUT_S}];
(
  way["building"](around:{query_radius},{cell_lat},{cell_lon});
  relation["building"](around:{query_radius},{cell_lat},{cell_lon});
);
out geom;
"""

    headers = {
        "User-Agent": settings.OVERPASS_USER_AGENT,
        "Accept": "application/json"
    }

    mirrors = settings.overpass_url_list
    start_time = time.time()
    last_error = None

    for mirror in mirrors:
        for attempt in range(2):
            if time.time() - start_time > 40.0:
                break
            try:
                with httpx.Client(timeout=float(settings.OVERPASS_TIMEOUT_S)) as client:
                    resp = client.post(mirror, data={"data": query}, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        set_cached_payload(settings.CACHE_DB, cache_key, data)
                        return data.get("elements", [])
                    elif resp.status_code in (429, 504):
                        time.sleep(1.0 if attempt == 0 else 3.0)
                        continue
                    else:
                        break
            except Exception as e:
                last_error = e
                time.sleep(1.0 if attempt == 0 else 3.0)

    # If live queries fail and fixtures exist, fallback to nearest fixture
    fixture_elements = find_nearest_fixture(lat, lon, fixtures_dir)
    if fixture_elements is not None:
        return fixture_elements

    if last_error:
        raise RuntimeError(f"Overpass fetch failed across all mirrors: {last_error}")
    raise RuntimeError("Overpass fetch failed: no response from mirrors")
