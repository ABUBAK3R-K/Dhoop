import os
import subprocess
import shutil
from typing import Optional

def encode_timelapse_video(
    frames_dir: str,
    output_mp4: str,
    fps: int = 4,
    timeout_s: int = 30
) -> str:
    """Encode PNG frames from frames_dir into an H.264 MP4 animation using ffmpeg.
    Command: ffmpeg -y -framerate 4 -i frames_hud/f%03d.png -c:v libx264 -pix_fmt yuv420p -movflags +faststart -an timelapse.mp4"""
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    
    input_pattern = os.path.join(frames_dir, "f%03d.png")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        output_mp4
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
        check=True
    )

    if not os.path.exists(output_mp4) or os.path.getsize(output_mp4) == 0:
        raise RuntimeError("ffmpeg failed to generate output video file")
        
    return output_mp4
