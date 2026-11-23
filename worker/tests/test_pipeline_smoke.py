import os
import pytest
from app.config import settings
from dhoop.pipeline import run_job_pipeline

def test_pipeline_smoke_with_fixture(tmp_path):
    """Smoke test running Dhoop Solar pipeline with campus fixture in offline mode."""
    old_fixtures_setting = settings.DEMO_FIXTURES
    settings.DEMO_FIXTURES = 1
    
    test_job_dir = str(tmp_path / "smoke_solar_job")
    
    try:
        result = run_job_pipeline(
            job_id="smoke_solar_001",
            lat=13.0185,
            lon=77.5650,
            floor=3,
            facing="E",
            target_date="2026-11-23",
            radius_m=300.0,
            job_dir=test_job_dir,
            meta={"chat_id": 123456}
        )

        assert result["status"] == "done"
        assert result["job_id"] == "smoke_solar_001"
        assert len(result["days"]) == 3

        # Verify Dhoop Solar qualification metrics
        assert "solar" in result
        solar = result["solar"]
        assert solar["grade"] in ("A", "B", "C", "D")
        assert "usable_solar_area_m2" in solar
        assert "suggested_kwp" in solar
        assert "recommendation" in solar

        # Verify confidence structure
        conf = result["confidence"]
        assert conf["level"] in ("high", "medium", "low")
        assert "pct_est" in conf

        # Verify site data
        site = result["site"]
        assert site["buildings_loaded"] > 0
        assert "height_coverage" in site

        # Verify result.json written to disk
        assert os.path.exists(os.path.join(test_job_dir, "result.json"))

    finally:
        settings.DEMO_FIXTURES = old_fixtures_setting
