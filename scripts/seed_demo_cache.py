"""Pre-warm the cache and populate SQLite cache for the 3 demo locations."""

import os
import sys
import json
import sqlite3
import time

# Add worker to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker")))
from app.config import settings

def seed():
    fixtures_dir = os.path.join(os.path.dirname(__file__), "..", "worker", "tests", "fixtures")
    db_path = settings.CACHE_DB
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS overpass_cache (
                key TEXT PRIMARY KEY,
                fetched_at INTEGER NOT NULL,
                payload BLOB NOT NULL
            )
        """)
        
        for name in ["campus.json", "residential.json", "open_area.json"]:
            fpath = os.path.join(fixtures_dir, name)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                meta = data.get("meta", {})
                lat = meta.get("lat")
                lon = meta.get("lon")
                if lat is not None and lon is not None:
                    cell_lat = round(lat / 0.002) * 0.002
                    cell_lon = round(lon / 0.002) * 0.002
                    cache_key = f"{cell_lat:.3f}:{cell_lon:.3f}:300"
                    payload = json.dumps(data).encode("utf-8")
                    conn.execute(
                        "INSERT OR REPLACE INTO overpass_cache (key, fetched_at, payload) VALUES (?, ?, ?)",
                        (cache_key, int(time.time()), payload)
                    )
                    print(f"Seeded cache key: {cache_key} ({meta.get('name')})")

        conn.commit()
    print("Demo cache pre-warming complete.")

if __name__ == "__main__":
    seed()
