from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Public / n8n
    PUBLIC_URL: str = "https://your-fixed-domain.example"
    N8N_VERSION: str = "1.66.0"
    N8N_ENCRYPTION_KEY: str = "change-me-long-random-encryption-key-for-n8n"
    NGROK_AUTHTOKEN: Optional[str] = None
    NGROK_DOMAIN: Optional[str] = None

    # Worker <-> n8n
    DHOOP_CALLBACK_SECRET: str = "change-me-long-random-dhoop-secret"
    DHOOP_CALLBACK_DEFAULT: str = "http://n8n:5678/webhook/dhoop-result"

    # Overpass
    OVERPASS_URLS: str = "https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter"
    OVERPASS_USER_AGENT: str = "Dhoop/0.1 (contact: dhoop@example.com)"
    OVERPASS_TIMEOUT_S: int = 25

    # Model / render
    RADIUS_M: float = 300.0
    VIEW_RADIUS_M: float = 180.0
    FLOOR_HEIGHT_M: float = 3.0
    SAMPLE_HEIGHT_OFFSET_M: float = 1.2
    DEFAULT_BUILDING_HEIGHT_M: float = 9.0
    MIN_SUN_ELEVATION_DEG: float = 5.0
    SUN_STEP_MIN: int = 5
    FRAME_STEP_MIN: int = 30
    MAX_FRAMES: int = 26
    RENDER_SIZE: int = 720
    RENDER_SAMPLES: int = 24
    RENDER_FPS: int = 4

    # Ops
    WORKER_CONCURRENCY: int = 1
    JOB_TIMEOUT_S: int = 240
    BLENDER_STAGE_TIMEOUT_S: int = 150
    ARTIFACT_TTL_HOURS: int = 24
    RATE_LIMIT_PER_HOUR: int = 5
    DEMO_FIXTURES: int = 0
    CACHE_DB: str = "/data/cache.sqlite"
    JOBS_DIR: str = "/data/jobs"
    PIPELINE_VERSION: str = "0.1.0"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    @property
    def overpass_url_list(self) -> List[str]:
        return [u.strip() for u in self.OVERPASS_URLS.split(",") if u.strip()]

settings = Settings()
