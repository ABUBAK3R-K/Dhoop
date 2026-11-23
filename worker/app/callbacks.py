import time
import httpx
from typing import Dict, Any, Optional
from app.config import settings

def send_callback(
    callback_url: str,
    payload: Dict[str, Any],
    secret: Optional[str] = None,
    max_retries: int = 3
) -> bool:
    """POST job completion payload to callback_url with header X-Dhoop-Secret and retries (2s, 5s, 15s)."""
    if not callback_url:
        return False

    secret_val = secret or settings.DHOOP_CALLBACK_SECRET
    headers = {
        "Content-Type": "application/json",
        "X-Dhoop-Secret": secret_val
    }

    backoffs = [2.0, 5.0, 15.0]

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(callback_url, json=payload, headers=headers)
                if resp.status_code in (200, 201, 202, 204):
                    return True
        except Exception:
            pass

        if attempt < len(backoffs):
            time.sleep(backoffs[attempt])

    return False
