# Dhoop Solar — Design Document (Conversation · Visual · Heatmap)

**Version:** 0.2 (Commercial Pivot) · Pairs with `prd.md` and `architecture.md`.  
Scope: Conversation UX for solar installers and homeowners, 3D rooftop solar heatmap, executive lead qualification card, and n8n canvas presentation.

---

## 1. Design Principles

1. **Installer-First Speed**: A sales rep gets a clear **Qualify / Disqualify** verdict in seconds without manual measurement.
2. **Actionable Sizing**: Direct translation from unshaded shadow-free area to **Suggested kWp** ($10\text{ m}^2 \approx 1\text{ kWp}$) mapped to PM Surya Ghar subsidy tiers (1 kW, 2 kW, 3 kW).
3. **Visual Credibility**: The 3D animation clearly shows why parts of the roof are shaded (e.g., neighbor's 4-story block casting morning shadow).
4. **Honest Boundaries**: Clear distinction between macro block shading (calculated via 3D building models) and micro rooftop obstructions (water tanks/parapets).

---

## 2. Conversation Flow & Telegram UX

```
User (Installer / Rep) ──📍 Location Pin ──────────────────────────────────────┐
                                                                              ▼
Bot:  "Found building: ~135 m² roof, ~3 floors. Confirm rooftop solar audit?"
      [ Confirm Solar Audit ] [ Change Floors ]
                                                                              │ tap
                                                                              ▼
Bot:  "Simulating seasonal shadows over rooftop grid… (~45 s)"   (action: upload_video)
                                                                              │
                                                                              ▼
Bot:  🎞 3D Rooftop Solar Heatmap Video (Loops as Animation)
Bot:  ☀️ Executive Solar Lead Qualification Card (Grade, kWp, Usable Area, Next Step)
```

### 2.1 Copy Library

**/start**
> Welcome to **Dhoop Solar** (धूप Solar) ☀️
> Automated rooftop shade qualification for solar installers and PM Surya Ghar applicants.
> Send me a location pin: 📎 → **Location** → drop pin on the building.

**/about**
> **Dhoop Solar** calculates rooftop solar viability by ray-casting sun positions across a 1.5 m rooftop grid against surrounding OpenStreetMap 3D buildings.
> It reports Grade A–D rating, unshaded usable roof area, and suggested system capacity.
> *Note: Micro-obstructions like water tanks and parapets are confirmed during physical site inspection.*

**Executive Lead Qualification Card**

```html
☀️ <b>Dhoop Solar — Rooftop Qualification Audit</b>

🏆 <b>Rooftop Rating: Grade B (Good Solar)</b>
⚡ <b>Suggested Capacity: 3.2 kWp</b>
📐 <b>Usable Solar Area: 32 m² (345 sq ft)</b> / 54 m² total (59% unshaded)

📅 <b>Shadow-Free Sunlight Hours</b>:
• <b>Winter (Dec 21)</b>: 4 h 15 m (10:15 AM – 02:30 PM)
• <b>Today (Nov 23)</b>: 5 h 10 m
• <b>Summer (Jun 21)</b>: 6 h 45 m

💡 <b>Installer Verdict</b>: <b>QUALIFIED LEAD</b>. Roof accommodates standard 3 kW PM Surya Ghar system on the South/Center quadrant.
⚠️ <i>Notice: Macro block shadows simulated from 3D map data. Rooftop parapets, Sintex water tanks, and stair-heads require physical site verification.</i>
Data © OpenStreetMap contributors
```

---

## 3. Visual Design — Rooftop Solar Heatmap Time-lapse

### 3.1 3D Scene Styling (Blender Cycles CPU)

- **Perspective**: Orthographic camera looking North from ~55° elevation angle framing a 180 m radius.
- **Host Building & Roof**:
  - Host building rendered in neutral light stone (`#F0DFC8`).
  - **Rooftop Grid Overlay**: A grid of cells ($1.5\text{ m} \times 1.5\text{ m}$) elevated 0.1 m above the host roof.
  - **Cell Solar Heatmap Coloring**:
    - **Prime Solar ($\ge 4.5\text{ h}$ direct sun)**: Vibrant Green (`#2ECC71`).
    - **Good Solar ($3.5\text{ h} - 4.5\text{ h}$)**: Gold / Amber (`#F1C40F`).
    - **Shaded / Poor ($< 3.5\text{ h}$)**: Deep Blue / Navy (`#2C3E50`).
- **Real-Time Shadow Animation**: Dynamic building shadows sweep across the ground and across the host rooftop grid as the sun moves from East to West.

### 3.2 HUD Overlay (Pillow 720×720)

```
┌───────────────────────────────────────────────┐
│ [ 11:30 AM ]           [ GRADE B · 3.2 kWp ]  │  ← Top HUD chips
│                                        N ↑    │
│                 3D Buildings                  │
│             [ Rooftop Solar Grid ]            │
│            (Green = Solar Zone)               │
│                                               │
│ █  32 m² Usable Solar Area (59% Unshaded)     │  ← Metric strip
│ © OpenStreetMap contributors · Dhoop Solar    │  ← Attribution
└───────────────────────────────────────────────┘
```

- **Top-Left Chip**: Local time chip `[ 11:30 AM ]`.
- **Top-Right Chip**: Grade badge & capacity `[ GRADE B · 3.2 kWp ]`.
- **Bottom Metric Bar**: Total vs Usable roof area and percentage unshaded.
- **Attribution**: Legal ODbL attribution.
