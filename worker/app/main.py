import os
import sys
import shutil
import subprocess
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import (
    CreateJobRequest,
    CreateJobResponse,
    JobStatusResponse,
    HealthzResponse
)
from app.jobs import job_manager

bpy_version_cached = "unknown"

def probe_bpy_version() -> str:
    """Check bpy version without importing bpy into the FastAPI process."""
    try:
        res = subprocess.run(
            [sys.executable, "-c", "import bpy; print(bpy.app.version_string)"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "bpy_available"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bpy_version_cached
    bpy_version_cached = probe_bpy_version()
    await job_manager.start()
    yield
    await job_manager.stop()

app = FastAPI(
    title="Dhoop Sunlight Audit Worker",
    version=settings.PIPELINE_VERSION,
    lifespan=lifespan
)

web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web"))
if os.path.exists(web_dir):
    assets_dir = os.path.join(web_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", response_class=FileResponse)
    async def serve_index():
        return FileResponse(os.path.join(web_dir, "index.html"))

@app.get("/healthz", response_model=HealthzResponse)
async def healthz():
    ffmpeg_ok = bool(shutil.which("ffmpeg"))
    return {
        "ok": True,
        "bpy": bpy_version_cached,
        "ffmpeg": ffmpeg_ok
    }

@app.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=CreateJobResponse)
async def create_job(req: CreateJobRequest):
    # Check rate limit
    chat_id = req.meta.get("chat_id") if req.meta else None
    if not job_manager.check_rate_limit(chat_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: 5 jobs per hour allowed"
        )

    job_id, is_cached = await job_manager.enqueue_job(req.model_dump())
    status_str = "done" if is_cached else "queued"
    return {
        "job_id": job_id,
        "status": status_str,
        "cached": is_cached
    }

@app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    return {
        "job_id": job["job_id"],
        "status": job.get("status", "unknown"),
        "cached": job.get("cached", False),
        "result": job.get("result"),
        "error": job.get("error")
    }

@app.get("/v1/jobs/{job_id}/artifacts/{artifact_name}")
async def get_job_artifact(job_id: str, artifact_name: str):
    job_dir = os.path.join(settings.JOBS_DIR, job_id)
    artifact_path = os.path.join(job_dir, artifact_name)

    # Security check: prevent directory traversal
    real_job_dir = os.path.realpath(job_dir)
    real_artifact_path = os.path.realpath(artifact_path)
    if not real_artifact_path.startswith(real_job_dir):
        raise HTTPException(status_code=403, detail="Forbidden")

    if not os.path.exists(artifact_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_name} not found"
        )

    media_type = "application/octet-stream"
    if artifact_name.endswith(".mp4"):
        media_type = "video/mp4"
    elif artifact_name.endswith(".png"):
        media_type = "image/png"
    elif artifact_name.endswith(".json"):
        media_type = "application/json"

    return FileResponse(artifact_path, media_type=media_type, filename=artifact_name)
