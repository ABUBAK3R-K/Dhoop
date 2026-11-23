import json
import os
from typing import List, Dict, Any, Optional

def compute_confidence(
    explicit_share: float,
    buildings_loaded: int,
    host_building_known: bool
) -> Dict[str, str]:
    """Determine confidence level and reason per design.md §5:
    - High: >= 70% explicit heights AND host building known
    - Medium: 35-69% explicit, OR host unknown
    - Low: < 35% explicit, OR < 8 buildings loaded"""
    pct_est = int(round((1.0 - explicit_share) * 100))
    
    if buildings_loaded < 8 or explicit_share < 0.35:
        level = "low"
        reason = f"{pct_est}% of nearby building heights are estimated (< 8 buildings mapped)"
    elif explicit_share >= 0.70 and host_building_known:
        level = "high"
        reason = f"{pct_est}% of nearby building heights are estimated"
    else:
        level = "medium"
        reason = f"{pct_est}% of nearby building heights are estimated"

    return {
        "level": level,
        "label": level.capitalize(),
        "pct_est": pct_est,
        "reason": reason
    }

def compute_solar_qualification(
    roof_area_m2: float,
    cell_winter_hours: List[float],
    today_hours_avg: float,
    jun_hours_avg: float,
    winter_threshold_hours: float = 4.0
) -> Dict[str, Any]:
    """Calculate commercial rooftop solar qualification metrics:
    - Usable shadow-free roof area (m2 and sq ft)
    - Suggested system capacity in kWp (10 m2 / kWp)
    - Rooftop Solar Grade (A-D) based on winter solstice shadow-free hours
    - PM Surya Ghar lead recommendation"""
    n_cells = len(cell_winter_hours)
    if n_cells == 0:
        n_cells = 1
        cell_winter_hours = [0.0]

    winter_avg = round(sum(cell_winter_hours) / n_cells, 2)
    usable_cells = sum(1 for h in cell_winter_hours if h >= winter_threshold_hours)
    usable_fraction = usable_cells / n_cells
    usable_pct = round(usable_fraction * 100.0, 1)

    usable_area_m2 = round(roof_area_m2 * usable_fraction, 1)
    total_sqft = int(round(roof_area_m2 * 10.7639))
    usable_sqft = int(round(usable_area_m2 * 10.7639))

    # Suggested system capacity: 10 m2 per kWp
    suggested_kwp = round(max(usable_area_m2 / 10.0, 0.0), 1)

    # Solar Grade A–D
    if usable_pct >= 80.0:
        grade = "A"
        grade_title = "Prime Solar"
        recommendation = "QUALIFIED LEAD: Prime unshaded roof. Recommended for maximum PM Surya Ghar subsidy capacity (3–5 kWp)."
    elif usable_pct >= 60.0:
        grade = "B"
        grade_title = "Good Solar"
        recommendation = "QUALIFIED LEAD: Recommended for standard 3 kWp PM Surya Ghar system on designated unshaded solar zone."
    elif usable_pct >= 40.0:
        grade = "C"
        grade_title = "Marginal Solar"
        recommendation = "PARTIAL LEAD: Partial solar viable (1–2 kWp). Consider elevated mounting structure to clear low winter shadows."
    else:
        grade = "D"
        grade_title = "Unviable / Heavy Shade"
        recommendation = "DISQUALIFIED LEAD: Heavy shadow occlusion from neighbouring structures (< 40% unshaded). Do not dispatch site visit."

    return {
        "grade": grade,
        "grade_title": grade_title,
        "total_roof_area_m2": roof_area_m2,
        "total_roof_area_sqft": total_sqft,
        "usable_solar_area_m2": usable_area_m2,
        "usable_solar_area_sqft": usable_sqft,
        "usable_percentage": usable_pct,
        "suggested_kwp": suggested_kwp,
        "grid_points_count": n_cells,
        "winter_sun_hours_avg": winter_avg,
        "recommendation": recommendation
    }

def format_hours_and_minutes(decimal_hours: float) -> str:
    """Format decimal hours into '3 h 40 m' style string."""
    total_minutes = int(round(decimal_hours * 60))
    h = total_minutes // 60
    m = total_minutes % 60
    if h == 0 and m == 0:
        return "No direct sun"
    if m == 0:
        return f"{h} h"
    if h == 0:
        return f"{m} m"
    return f"{h} h {m} m"

def format_summary_html(report_data: Dict[str, Any]) -> str:
    """Build the final Executive Solar Lead Qualification Card for Telegram."""
    solar = report_data.get("solar", {})
    grade = solar.get("grade", "B")
    grade_title = solar.get("grade_title", "Good Solar")
    kwp = solar.get("suggested_kwp", 3.0)
    usable_m2 = solar.get("usable_solar_area_m2", 30.0)
    usable_sqft = solar.get("usable_solar_area_sqft", 320)
    total_m2 = solar.get("total_roof_area_m2", 50.0)
    usable_pct = solar.get("usable_percentage", 60.0)
    recom = solar.get("recommendation", "Qualified for PM Surya Ghar.")

    days = report_data.get("days", [])
    today_info = next((d for d in days if d.get("label") == "today"), {})
    dec_info = next((d for d in days if d.get("label") == "dec21"), {})
    jun_info = next((d for d in days if d.get("label") == "jun21"), {})

    def format_windows(w_list: List[List[str]]) -> str:
        if not w_list:
            return "No direct sun"
        return ", ".join(f"{w[0]}–{w[1]}" for w in w_list)

    today_hours = format_hours_and_minutes(today_info.get("sun_hours", 0.0))
    dec_hours = format_hours_and_minutes(dec_info.get("sun_hours", 0.0))
    jun_hours = format_hours_and_minutes(jun_info.get("sun_hours", 0.0))

    dec_windows = format_windows(dec_info.get("windows", []))

    conf = report_data.get("confidence", {})
    conf_label = conf.get("label", "Medium")
    pct_est = conf.get("pct_est", 50)

    html = f"""☀️ <b>Dhoop Solar — Rooftop Qualification Audit</b>

🏆 <b>Rooftop Rating: Grade {grade} ({grade_title})</b>
⚡ <b>Suggested Capacity: {kwp} kWp</b>
📐 <b>Usable Solar Area: {usable_m2} m² ({usable_sqft} sq ft)</b> / {total_m2} m² total ({usable_pct}% unshaded)

📅 <b>Shadow-Free Sunlight Hours</b>:
• <b>Winter (Dec 21)</b>: {dec_hours} ({dec_windows})
• <b>Today</b>: {today_hours}
• <b>Summer (Jun 21)</b>: {jun_hours}

💡 <b>Installer Verdict</b>: {recom}

<b>Confidence: {conf_label}</b> — {pct_est}% of nearby building heights estimated.
⚠️ <i>Notice: Macro block shadows simulated from 3D map data. Rooftop water tanks, parapets, stair-heads, and trees require physical site verification.</i>
Data © OpenStreetMap contributors"""

    return html
