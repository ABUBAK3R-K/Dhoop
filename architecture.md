# Dhoop Solar — Architecture

**Version:** 0.2 (Commercial Pivot) · Pairs with `prd.md` and `design.md`.  
This document defines the technical contract for **Dhoop Solar**: rooftop discretization, multi-point BVH solar ray-casting, unshaded area calculation, suggested kW sizing, Rooftop Solar Grade (A–D), Cycles rendering, and API schemas.

---

## 1. System Overview

```
                         HTTPS (tunnel)                        Docker network "dhoop_default"
┌────────────┐     ┌──────────────────────┐        ┌──────────────────────────────────────────────┐
│  Telegram  │◀───▶│  Telegram Bot API    │        │                                              │
│  (Installer│     └──────────┬───────────┘        │   ┌────────────┐  POST /v1/jobs  ┌─────────┐ │
│  or Rep)   │                │ webhook            │   │    n8n     │────────────────▶│ worker  │ │
└────────────┘                │                    │   │ intake WF  │                 │ FastAPI │ │
                              ▼                    │   │ result WF  │◀────────────────│ + bpy   │ │
                   ┌─────────────────┐  :5678      │   │ ops WF     │  callback POST  │ ffmpeg  │ │
                   │ tunnel (ngrok / │────────────▶│   │            │                 └────┬────┘ │
                   │ cloudflared)    │             │   └────────────┘                      │      │
                   └─────────────────┘             │                                       ▼      │
                                                   │            volume: dhoop_data                │
                                                   │            /data/jobs, /data/cache.sqlite    │
                                                   └──────────────────────────────────────────────┘
                                                                         │ HTTPS (egress)
                                                                         ▼
                                                           Overpass API (mirror list)
```

### Division of Labour

| Component | Responsibility | Why Load-Bearing |
|---|---|---|
| **n8n** | Conversation flow, location handling, job queuing, async delivery, error alerting. | Low-code orchestration ready for rapid installer CRM / webhook integrations. |
| **Docker** | Headless Linux container isolating Python 3.11, `bpy 4.5`, ffmpeg, and math/geometry libraries. | Reproducible CPU-bound environment with strict resource limits. |
| **Blender (`bpy`)** | Headless Cycles CPU engine; builds 3D scene from OSM footprints, constructs BVH tree, **ray-casts rooftop grid**, and **renders solar heatmap time-lapse**. | Guarantees identical 3D physics for both the quantitative numbers and the video proof. |
| **Worker (FastAPI)** | Job scheduling, rooftop grid generator, SQLite caching, rate limiting, and webhook callbacks. | Clean, typed microservice decoupling orchestration from heavy computation. |

---

## 2. Rooftop Solar Qualification Algorithms

### 2.1 Rooftop Discretization (`geometry.py`)

When the host building polygon $P$ and height $H$ are identified:
1. Inset polygon by 0.5 m to avoid edge artifacts: $P_{\text{safe}} = P.\text{buffer}(-0.5)$. If $P_{\text{safe}}$ is empty or invalid, fallback to $P$.
2. Discretize into a regular grid with spacing $s = 1.5\text{ m}$.
3. Generate sample points:
   $$G = \{(x_i, y_i, H + 0.1) \mid (x_i, y_i) \in P_{\text{safe}}\}$$
4. Total Roof Area $A_{\text{total}} = P.\text{area}$.
5. Each grid cell represents effective area $A_{\text{cell}} = \frac{A_{\text{total}}}{|G|}$.

```python
def generate_rooftop_grid(poly: Polygon, height_m: float, spacing_m: float = 1.5) -> List[List[float]]:
    safe_poly = poly.buffer(-0.5)
    if safe_poly.is_empty or not safe_poly.is_valid:
        safe_poly = poly
    minx, miny, maxx, maxy = safe_poly.bounds
    points = []
    x = minx + spacing_m / 2.0
    while x < maxx:
        y = miny + spacing_m / 2.0
        while y < maxy:
            pt = Point(x, y)
            if safe_poly.contains(pt):
                points.append([round(x, 2), round(y, 2), round(height_m + 0.1, 2)])
            y += spacing_m
        x += spacing_m
    return points
```

### 2.2 Multi-Point BVH Ray-Casting (`blender_stage.py`)

For each time step $t$ across the reference dates (Today, Dec 21, Jun 21):
1. Compute sun vector $S(t) = (\cos(\text{el})\sin(\text{az}), \cos(\text{el})\cos(\text{az}), \sin(\text{el}))$.
2. If sun elevation $\text{el} < 5^\circ$, all points are shaded.
3. For each rooftop point $g_i \in G$, cast a ray from $g_i + 0.05 \cdot S$ towards $S$.
4. Check intersection against neighboring building occluder mesh `others` in the `BVHTree`.
5. Accumulate shadow-free hours per cell $i$:
   $$h_i = \sum_{t} \text{is\_sunlit}(g_i, t) \times \frac{\text{step\_min}}{60}$$

### 2.3 Solar Sizing & Rooftop Grade

1. **Usable Cell Condition**: A cell is qualified as unshaded solar area if its winter (Dec 21) shadow-free hours $\ge 4.0\text{ h}$ (or annual equivalent).
2. **Usable Area**:
   $$f_{\text{usable}} = \frac{|\{i \mid h_{i, \text{dec21}} \ge 4.0\}|}{|G|}, \quad A_{\text{usable}} = A_{\text{total}} \times f_{\text{usable}}$$
3. **Suggested System Capacity ($\text{kWp}$)**:
   $$\text{kWp} = \text{round}\left(\frac{A_{\text{usable}}}{10.0}, 1\right)$$
   *(Rule of thumb: $\approx 10\text{ m}^2$ or 100 sq ft unshaded area per $1\text{ kWp}$ panel capacity).*
4. **Rooftop Solar Grade (A–D)**:
   - **Grade A (Prime)**: $f_{\text{usable}} \ge 0.80$ ($\ge 80\%$ unshaded, $\ge 4.5\text{ h}$ avg). Maximum PM Surya Ghar qualification.
   - **Grade B (Good)**: $0.60 \le f_{\text{usable}} < 0.80$ ($60\%–79\%$ unshaded, $\ge 4.0\text{ h}$ avg). Recommended for standard 3 kW system.
   - **Grade C (Marginal)**: $0.40 \le f_{\text{usable}} < 0.60$ ($40\%–59\%$ unshaded). Requires elevated structure.
   - **Grade D (Unviable)**: $f_{\text{usable}} < 0.40$ ($< 40\%$ unshaded). **Lead Disqualified**.

---

## 3. Data Schema: `result.json`

```json
{
  "job_id": "01JABCDEF...",
  "status": "done",
  "cached": false,
  "site": {
    "host_building": {"osm_id": "way/1001", "height_m": 12.0, "height_source": "levels"},
    "buildings_loaded": 48,
    "height_coverage": {"explicit": 0.65, "estimated": 0.35}
  },
  "solar": {
    "grade": "B",
    "grade_title": "Good Solar",
    "total_roof_area_m2": 65.0,
    "total_roof_area_sqft": 700,
    "usable_solar_area_m2": 42.5,
    "usable_solar_area_sqft": 457,
    "usable_percentage": 65.4,
    "suggested_kwp": 4.2,
    "grid_points_count": 28,
    "winter_sun_hours_avg": 4.3,
    "recommendation": "QUALIFIED LEAD: Roof accommodates a 3-4 kW PM Surya Ghar system."
  },
  "days": [
    {"label": "today", "date": "2026-11-23", "sun_hours": 5.2, "windows": [["08:15", "13:30"]]},
    {"label": "dec21", "date": "2026-12-21", "sun_hours": 4.3, "windows": [["09:30", "13:45"]]},
    {"label": "jun21", "date": "2027-06-21", "sun_hours": 6.8, "windows": [["07:00", "13:50"]]}
  ],
  "confidence": {
    "level": "high",
    "reason": "35% of nearby building heights are estimated"
  },
  "warnings": [
    "Macro building shadows simulated from OpenStreetMap.",
    "Rooftop water tanks, parapets, stair-heads, and trees require final on-site physical survey."
  ],
  "artifacts": {
    "video": "timelapse.mp4",
    "result": "result.json"
  },
  "timing_ms": {
    "fetch": 1800,
    "parse": 60,
    "geometry": 120,
    "sun": 80,
    "blender": 22000,
    "compose": 850,
    "ffmpeg": 600,
    "total": 25510
  }
}
```

---

## 4. Blender 3D Scene & Heatmap Rendering

1. **Scene Setup**:
   - `scene.render.engine = 'CYCLES'`, `device = 'CPU'`, samples = 24.
   - Camera: Orthographic fixed framing at ~55° tilt from South.
   - Ground plane at $Z=0$ in warm neutral (`#E8E3D8`).
   - Neighbor buildings in matte stone (`#F6F3EC`).
   - Host building in distinctive warm tint (`#F0DFC8`).
2. **Rooftop Grid Mesh**:
   - For each rooftop grid cell, a thin quad patch is generated on the roof surface.
   - Cell color encodes solar exposure:
     - $\ge 4.5\text{ h}$ direct sun: `#2ECC71` (Vibrant Solar Green)
     - $3.5\text{ h} - 4.5\text{ h}$: `#F1C40F` (Solar Gold)
     - $< 3.5\text{ h}$: `#2C3E50` (Shadow Navy)
3. **Dynamic Shadows**:
   - Sun lamp rotates per frame according to $(az(t), el(t))$.
   - Cycles renders cast shadows falling realistically across the neighborhood and across the colored rooftop grid.
