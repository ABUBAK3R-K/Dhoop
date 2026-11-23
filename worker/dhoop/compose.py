import os
import math
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont

# Colors from design.md §3.4
COLOR_SUN = (46, 204, 113)          # #2ECC71 (Solar Green)
COLOR_SHADE = (44, 62, 80)          # #2C3E50 (Navy)
COLOR_HUD_BG = (18, 22, 33, 190)    # rgba(18, 22, 33, 0.75)
COLOR_WHITE = (255, 255, 255, 255)
COLOR_GOLD = (241, 196, 15, 255)    # #F1C40F
COLOR_TEXT_DIM = (255, 255, 255, 204)

def get_font(size: int) -> ImageFont.ImageFont:
    """Load bundled Inter SemiBold font or fallback to system DejaVu/default."""
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "assets", "Inter-SemiBold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_hud_chips(
    draw: ImageDraw.ImageDraw,
    width: int,
    time_label: str,
    solar_badge: str,
    font_time: ImageFont.ImageFont,
    font_badge: ImageFont.ImageFont
):
    """Draw top-left time chip and top-right solar rating chip."""
    margin = 24
    radius = 12
    chip_h = 42

    # Top-Left: Time chip [ 09:30 AM ]
    time_text = f" {time_label} "
    time_bbox = draw.textbbox((0, 0), time_text, font=font_time)
    text_w = time_bbox[2] - time_bbox[0]
    time_w = max(text_w + 24, 140)
    
    draw.rounded_rectangle(
        [margin, margin, margin + time_w, margin + chip_h],
        radius=radius,
        fill=COLOR_HUD_BG
    )
    draw.text(
        (margin + 12, margin + 8),
        time_text,
        font=font_time,
        fill=COLOR_WHITE
    )

    # Top-Right: Solar rating chip [ GRADE B · 3.2 kWp ]
    badge_text = f" {solar_badge} "
    badge_bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    badge_text_w = badge_bbox[2] - badge_bbox[0]
    badge_w = max(badge_text_w + 24, 160)
    badge_x = width - margin - badge_w

    draw.rounded_rectangle(
        [badge_x, margin, badge_x + badge_w, margin + chip_h],
        radius=radius,
        fill=COLOR_HUD_BG
    )
    draw.text(
        (badge_x + 12, margin + 9),
        badge_text,
        font=font_badge,
        fill=COLOR_GOLD
    )

def draw_metric_bar(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    usable_m2: float,
    usable_pct: float,
    font_metric: ImageFont.ImageFont
):
    """Draw bottom solar metric bar above attribution."""
    margin = 24
    bar_y = height - margin - 38
    metric_text = f"☀️ {usable_m2} m² Usable Solar Area ({usable_pct}% unshaded)"
    draw.rounded_rectangle(
        [margin, bar_y, width - margin, bar_y + 24],
        radius=6,
        fill=COLOR_HUD_BG
    )
    draw.text((margin + 12, bar_y + 3), metric_text, font=font_metric, fill=COLOR_WHITE)

def draw_attribution(draw: ImageDraw.ImageDraw, width: int, height: int, font_attr: ImageFont.ImageFont):
    """Draw ODbL legal attribution at bottom edge."""
    attr_text = "© OpenStreetMap contributors · Dhoop Solar"
    draw.text((24, height - 26), attr_text, font=font_attr, fill=COLOR_TEXT_DIM)

def compose_frames(
    raw_frames_dir: str,
    out_dir: str,
    frame_samples: List[Dict[str, Any]],
    frame_sunlit: List[bool],
    solar_info: Optional[Dict[str, Any]] = None
) -> List[str]:
    """Overlay HUD, solar rating chip, and legal attribution onto each rendered frame."""
    os.makedirs(out_dir, exist_ok=True)
    font_time = get_font(20)
    font_badge = get_font(18)
    font_metric = get_font(14)
    font_attr = get_font(13)

    solar_info = solar_info or {}
    grade = solar_info.get("grade", "B")
    kwp = solar_info.get("suggested_kwp", 3.0)
    solar_badge = f"GRADE {grade} · {kwp} kWp"
    usable_m2 = solar_info.get("usable_solar_area_m2", 30.0)
    usable_pct = solar_info.get("usable_percentage", 60.0)

    composed_files = []
    total_frames = len(frame_samples)
    out_idx = 0

    for i, s in enumerate(frame_samples):
        fname = f"f{i:03d}.png"
        raw_path = os.path.join(raw_frames_dir, fname)
        if not os.path.exists(raw_path):
            continue

        base_img = Image.open(raw_path).convert("RGBA")
        overlay = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        iso_t = s.get("t", "")
        time_part = iso_t.split("T")[1][:5] if "T" in iso_t else ""
        try:
            hh, mm = map(int, time_part.split(":"))
            period = "AM" if hh < 12 else "PM"
            hh_12 = hh % 12
            if hh_12 == 0:
                hh_12 = 12
            display_time = f"{hh_12:02d}:{mm:02d} {period}"
        except Exception:
            display_time = time_part

        draw_hud_chips(draw, base_img.width, display_time, solar_badge, font_time, font_badge)
        draw_metric_bar(draw, base_img.width, base_img.height, usable_m2, usable_pct, font_metric)
        draw_attribution(draw, base_img.width, base_img.height, font_attr)

        final_img = Image.alpha_composite(base_img, overlay).convert("RGB")

        # Duplicate first and last frames for 1s orientation hold (4 fps)
        reps = 4 if (i == 0 or i == total_frames - 1) else 1
        for _ in range(reps):
            dup_name = f"f{out_idx:03d}.png"
            final_img.save(os.path.join(out_dir, dup_name))
            composed_files.append(dup_name)
            out_idx += 1

    return composed_files
