import os
import time
import json
import uuid
import hashlib
import asyncio
import sqlite3
import shutil
from typing import Dict, Any, Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.callbacks import send_callback
from dhoop.pipeline import run_job_pipeline

class JobManager:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=settings.WORKER_CONCURRENCY)
        self.worker_task: Optional[asyncio.Task] = None
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(os.path.abspath(settings.CACHE_DB)), exist_ok=True)
        os.makedirs(settings.JOBS_DIR, exist_ok=True)
        with sqlite3.connect(settings.CACHE_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit (
                    chat_id TEXT NOT NULL,
                    ts INTEGER NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_cache (
                    cache_key TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)
            conn.commit()

    def check_rate_limit(self, chat_id: Any) -> bool:
        """Returns True if request is allowed, False if limit exceeded."""
        if not chat_id:
            return True
        cid = str(chat_id)
        now = int(time.time())
        window_start = now - 3600
        try:
            with sqlite3.connect(settings.CACHE_DB) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM rate_limit WHERE chat_id = ? AND ts > ?", (cid, window_start))
                count = cur.fetchone()[0]
                if count >= settings.RATE_LIMIT_PER_HOUR:
                    return False
                conn.execute("INSERT INTO rate_limit (chat_id, ts) VALUES (?, ?)", (cid, now))
                conn.commit()
        except Exception:
            pass
        return True

    def compute_cache_key(self, lat: float, lon: float, floor: int, facing: str, date: Optional[str]) -> str:
        date_str = date or "default"
        raw_key = f"{lat:.5f}:{lon:.5f}:{floor}:{facing}:{date_str}:{settings.PIPELINE_VERSION}"
        return hashlib.sha1(raw_key.encode("utf-8")).hexdigest()

    def get_cached_job_id(self, cache_key: str) -> Optional[str]:
        try:
            with sqlite3.connect(settings.CACHE_DB) as conn:
                cur = conn.cursor()
                cur.execute("SELECT job_id, created_at FROM job_cache WHERE cache_key = ?", (cache_key,))
                row = cur.fetchone()
                if row:
                    job_id, created_at = row
                    # Verify job directory and result exist and within 24h
                    if time.time() - created_at < settings.ARTIFACT_TTL_HOURS * 3600:
                        job_dir = os.path.join(settings.JOBS_DIR, job_id)
                        res_path = os.path.join(job_dir, "result.json")
                        if os.path.exists(res_path):
                            return job_id
        except Exception:
            pass
        return None

    def set_cached_job(self, cache_key: str, job_id: str):
        try:
            with sqlite3.connect(settings.CACHE_DB) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO job_cache (cache_key, job_id, created_at) VALUES (?, ?, ?)",
                    (cache_key, job_id, int(time.time()))
                )
                conn.commit()
        except Exception:
            pass

    async def start(self):
        self.worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        self.executor.shutdown(wait=False)

    async def enqueue_job(self, job_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Enqueue a new job or return cached job. Returns (job_id, is_cached)."""
        lat = job_data["lat"]
        lon = job_data["lon"]
        floor = job_data["floor"]
        facing = job_data.get("facing", "ANY")
        date = job_data.get("date")

        cache_key = self.compute_cache_key(lat, lon, floor, facing, date)
        cached_id = self.get_cached_job_id(cache_key)

        if cached_id:
            # Deliver callback asynchronously even on cache hit so n8n has single delivery path
            callback_url = job_data.get("callback_url")
            if callback_url:
                res_path = os.path.join(settings.JOBS_DIR, cached_id, "result.json")
                if os.path.exists(res_path):
                    with open(res_path, "r", encoding="utf-8") as f:
                        cached_res = json.load(f)
                    cached_res["cached"] = True
                    cached_res["meta"] = job_data.get("meta", {})
                    asyncio.create_task(asyncio.to_thread(send_callback, callback_url, cached_res))
            return cached_id, True

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "data": job_data,
            "cache_key": cache_key,
            "created_at": time.time(),
            "result": None,
            "error": None
        }

        await self.queue.put(job_id)
        return job_id, False

    async def _worker_loop(self):
        while True:
            job_id = await self.queue.get()
            try:
                job_entry = self.jobs.get(job_id)
                if not job_entry:
                    continue
                job_entry["status"] = "running"
                job_data = job_entry["data"]

                loop = asyncio.get_running_loop()
                # Run pipeline in executor with hard timeout
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            self.executor,
                            run_job_pipeline,
                            job_id,
                            job_data["lat"],
                            job_data["lon"],
                            job_data["floor"],
                            job_data.get("facing"),
                            job_data.get("date"),
                            job_data.get("radius_m", 300.0),
                            None,
                            job_data.get("meta")
                        ),
                        timeout=float(settings.JOB_TIMEOUT_S)
                    )
                    job_entry["status"] = "done"
                    job_entry["result"] = result
                    self.set_cached_job(job_entry["cache_key"], job_id)

                    callback_url = job_data.get("callback_url")
                    if callback_url:
                        await asyncio.to_thread(send_callback, callback_url, result)

                except asyncio.TimeoutError:
                    job_entry["status"] = "failed"
                    job_entry["error"] = {"code": "TIMEOUT", "message": "Job timed out"}
                    callback_url = job_data.get("callback_url")
                    if callback_url:
                        fail_doc = {
                            "job_id": job_id,
                            "status": "failed",
                            "error": job_entry["error"],
                            "meta": job_data.get("meta", {})
                        }
                        await asyncio.to_thread(send_callback, callback_url, fail_doc)

                except Exception as e:
                    job_entry["status"] = "failed"
                    job_entry["error"] = {"code": "INTERNAL", "message": str(e)}
                    callback_url = job_data.get("callback_url")
                    if callback_url:
                        fail_doc = {
                            "job_id": job_id,
                            "status": "failed",
                            "error": job_entry["error"],
                            "meta": job_data.get("meta", {})
                        }
                        await asyncio.to_thread(send_callback, callback_url, fail_doc)

            finally:
                self.queue.task_done()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if job_id in self.jobs:
            return self.jobs[job_id]
        # Check disk if restarted
        job_dir = os.path.join(settings.JOBS_DIR, job_id)
        res_path = os.path.join(job_dir, "result.json")
        if os.path.exists(res_path):
            with open(res_path, "r", encoding="utf-8") as f:
                res = json.load(f)
            return {"job_id": job_id, "status": "done", "result": res}
        return None

job_manager = JobManager()
