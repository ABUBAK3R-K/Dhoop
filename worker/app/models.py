from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List

class CreateJobRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude of spot")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude of spot")
    floor: int = Field(0, ge=0, le=80, description="Floor index: 0=Ground, 2=2nd, etc.")
    facing: Optional[str] = Field("ANY", description="Facing direction: N, E, S, W, ANY")
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Optional YYYY-MM-DD")
    radius_m: float = Field(300.0, ge=100.0, le=400.0, description="Query radius in meters")
    callback_url: Optional[str] = Field(None, description="Webhook URL for result callback")
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary metadata e.g. chat_id")

    @field_validator("facing")
    @classmethod
    def validate_facing(cls, v: Optional[str]) -> str:
        if v is None:
            return "ANY"
        val = v.strip().upper()
        if val not in ("N", "E", "S", "W", "ANY"):
            raise ValueError("facing must be one of N, E, S, W, ANY")
        return val

class CreateJobResponse(BaseModel):
    job_id: str
    status: str
    cached: bool = False

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    cached: bool = False
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None

class HealthzResponse(BaseModel):
    ok: bool
    bpy: str
    ffmpeg: bool
