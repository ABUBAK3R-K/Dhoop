import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.jobs import job_manager

client = TestClient(app)

def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "bpy" in data
    assert "ffmpeg" in data

def test_create_job_validation_errors():
    # Invalid latitude (> 90)
    resp = client.post("/v1/jobs", json={"lat": 95.0, "lon": 77.59, "floor": 2})
    assert resp.status_code == 422

    # Invalid floor (< 0)
    resp = client.post("/v1/jobs", json={"lat": 12.97, "lon": 77.59, "floor": -1})
    assert resp.status_code == 422

    # Invalid floor (> 80)
    resp = client.post("/v1/jobs", json={"lat": 12.97, "lon": 77.59, "floor": 85})
    assert resp.status_code == 422

    # Invalid facing
    resp = client.post("/v1/jobs", json={"lat": 12.97, "lon": 77.59, "floor": 2, "facing": "XYZ"})
    assert resp.status_code == 422

def test_create_job_valid_enqueue():
    payload = {
        "lat": 12.9716,
        "lon": 77.5946,
        "floor": 5,
        "facing": "E",
        "radius_m": 300,
        "meta": {"chat_id": 99999}
    }
    resp = client.post("/v1/jobs", json=payload)
    assert resp.status_code == 202
    data = resp.json()
    assert "job_id" in data
    assert data["status"] in ("queued", "done")

def test_rate_limiting():
    import uuid
    chat_id = uuid.uuid4().int % 100000000
    payload = {
        "lat": 12.9716,
        "lon": 77.5946,
        "floor": 1,
        "meta": {"chat_id": chat_id}
    }

    # First 5 calls within the hour should pass (or return cached 202)
    for _ in range(5):
        resp = client.post("/v1/jobs", json=payload)
        assert resp.status_code == 202

    # 6th call from same chat_id must trigger 429 Too Many Requests
    resp = client.post("/v1/jobs", json=payload)
    assert resp.status_code == 429
    assert "Rate limit exceeded" in resp.json()["detail"]

def test_get_nonexistent_job():
    resp = client.get("/v1/jobs/nonexistent_job_12345")
    assert resp.status_code == 404

def test_create_job_and_poll_execution():
    from app.config import settings
    import time
    settings.DEMO_FIXTURES = 1
    with TestClient(app) as test_client:
        payload = {
            "lat": 13.0185,
            "lon": 77.5650,
            "floor": 2,
            "facing": "S",
            "radius_m": 300,
            "meta": {"test": "e2e"}
        }
        resp = test_client.post("/v1/jobs", json=payload)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        result_data = None
        t_start = time.time()
        while time.time() - t_start < 30:
            status_resp = test_client.get(f"/v1/jobs/{job_id}")
            assert status_resp.status_code == 200
            data = status_resp.json()
            if data["status"] == "done":
                result_data = data
                break
            time.sleep(0.5)

        assert result_data is not None, "Job execution did not complete within timeout"
        assert result_data["status"] == "done"
        assert "solar_qualification" in result_data["result"]
        sq = result_data["result"]["solar_qualification"]
        assert sq["rating"] in ("Grade A", "Grade B", "Grade C", "Grade D")
        assert sq["suggested_kwp"] > 0

