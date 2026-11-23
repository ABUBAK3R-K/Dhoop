"""Standalone CLI runner for Dhoop Solar rooftop qualification.
Usage:
    python scripts/run_solar_audit.py --fixture campus
    python scripts/run_solar_audit.py --lat 12.9780 --lon 77.6400
"""

import os
import sys
import argparse
import json

# Add worker to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "worker")))

from app.config import settings
from dhoop.pipeline import run_job_pipeline
from dhoop.report import format_summary_html

FIXTURE_COORDS = {
    "campus": (13.0185, 77.5650),
    "residential": (12.9780, 77.6400),
    "open_area": (12.9750, 77.5920)
}

def main():
    parser = argparse.ArgumentParser(description="Dhoop Solar — Rooftop Shade Qualifier")
    parser.add_argument("--fixture", choices=["campus", "residential", "open_area"], default="campus", help="Demo fixture name")
    parser.add_argument("--lat", type=float, default=None, help="Latitude")
    parser.add_argument("--lon", type=float, default=None, help="Longitude")
    parser.add_argument("--out-dir", type=str, default="./output_solar", help="Output directory")

    args = parser.parse_args()

    if args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
    else:
        lat, lon = FIXTURE_COORDS[args.fixture]
        settings.DEMO_FIXTURES = 1

    print(f"\n☀️ Running Dhoop Solar Audit for ({lat:.5f}, {lon:.5f})...\n")

    os.makedirs(args.out_dir, exist_ok=True)

    result = run_job_pipeline(
        job_id="cli_audit",
        lat=lat,
        lon=lon,
        floor=3,
        facing="S",
        radius_m=300.0,
        job_dir=args.out_dir
    )

    card_html = format_summary_html(result)
    print("=" * 60)
    # Strip basic HTML tags for clean console display
    console_text = (
        card_html.replace("<b>", "")
        .replace("</b>", "")
        .replace("<i>", "")
        .replace("</i>", "")
    )
    print(console_text)
    print("=" * 60)
    print(f"\nArtifacts saved to: {os.path.abspath(args.out_dir)}")
    print(f"• Summary JSON: {os.path.join(args.out_dir, 'result.json')}")
    if result["artifacts"]["video"]:
        print(f"• 3D Solar Time-lapse: {os.path.join(args.out_dir, result['artifacts']['video'])}")

if __name__ == "__main__":
    main()
