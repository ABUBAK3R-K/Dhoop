# Dhoop Solar — Rooftop Shade Qualifier for Solar Installers · PRD

**Version:** 0.2 (Commercial Pivot) · **Date:** 2026-11-23 · **Status:** Ready to build  
**Working title:** Dhoop Solar (धूप Solar) — Automated Rooftop Solar Qualification Bot  
**Stack constraint (hard):** n8n (automation & lead capture) + Docker (runtime) + Blender (3D engine, rooftop grid ray-casting & render). All three must be load-bearing.

---

## 1. Summary

**Dhoop Solar** is an instant rooftop shade qualification service delivered via chat and API. A solar installer sales rep, EPC contractor, or loan officer sends a **location pin** (or drops a pin on a client's building). Within 60 seconds, Dhoop Solar replies with:

1. **Rooftop Solar Rating (Grade A–D)** based on shadow-free sunlight hours across seasons.
2. **Usable Roof Area ($m^2$ / sq ft)**: total roof footprint minus areas shaded by neighboring buildings.
3. **Suggested System Capacity ($\text{kWp}$)**: actionable sizing based on unshaded contiguous area ($10\text{ m}^2 \approx 1\text{ kWp}$).
4. **Seasonal Shadow-Free Hours**: detailed sun availability for **Today**, the **Shortest Day (Dec 21)**, and the **Longest Day (Jun 21)**.
5. **Rendered 3D Solar Time-lapse (MP4)**: visual 3D simulation with a rooftop solar heatmap showing shadow movement and the unshaded solar installation zone.
6. **One-page Lead Qualification Report**: instantly shareable PDF/card to qualify or disqualify the site before committing to a costly physical site survey.

---

## 2. Market Opportunity & "Why Now"

- **PM Surya Ghar: Muft Bijli Yojana**: Launched with an outlay of **₹75,021 crore** aiming to install rooftop solar on **1 crore (10 million) households** by March 2027. The scheme crossed **50 lakh (5 million) registrations by August 2026**.
- **The Installer Bottleneck**: Customer acquisition and pre-installation site visits cost installers **₹1,500–₹3,000 per site** in truck rolls, technician time, and manual measurements. In dense Indian cities (Bengaluru, Delhi-NCR, Pune, Hyderabad), up to **40% of residential leads are disqualified on-site** because adjacent 4-to-6-story buildings cast massive winter shadows on the applicant's 2-or-3-story roof.
- **Regulatory Tailwinds**: Stakeholder proposals on the MNRE rooftop draft recommended rating consumer rooftops **A through D by shadow-free hours** to establish solar viability, grid feed-in potential, and loan eligibility.
- **Differentiation**: Zero-install, instant chat qualification, real 3D building occlusion from OpenStreetMap, rooftop grid ray-casting (not a single point), and visual 3D proof that both installers and customers understand immediately.

---

## 3. Target Customers & Who Pays

| Customer Segment | Pain Point | Willingness to Pay |
| --- | --- | --- |
| **Solar Installers & EPCs** (Primary) | Paying ₹2,000+ per wasted site visit on shadowed roofs; slow quote turnaround. | Pays per qualified lead check (e.g. ₹50–₹100/check) or monthly SaaS tier to filter pipeline. |
| **Solar Loan Lenders & NBFCs** (Secondary) | Need independent collateral validation that the funded rooftop gets sufficient sunlight to generate projected EMI savings. | Pays per loan underwriting check as part of digital technical verification. |
| **Sales Reps / Channel Partners** | Need instant answers while talking to a prospect on the phone or WhatsApp. | Uses the Telegram bot in the field for instant customer qualification. |
| **Proactive Homeowners** | Want to know if their roof qualifies for PM Surya Ghar subsidies before applying. | Free tier for consumer lead generation. |

Primary persona for the MVP demo: **Vikram, Solar Sales Engineer at an EPC firm** qualifying 10 inbound PM Surya Ghar leads per morning.

---

## 4. Goals and Non-Goals

**Goals (MVP)**

- G1. **Rooftop Grid Ray-Casting**: Identify the host building from a pin and sample a 1.5 m grid across the entire rooftop polygon.
- G2. **Quantitative Solar Metrics**: Accurately report Total Roof Area, Usable Unshaded Roof Area ($m^2$ and sq ft), Suggested $\text{kWp}$ capacity, and Rooftop Solar Grade (A–D).
- G3. **3D Visual Proof**: Render a 3D Cycles CPU shadow time-lapse featuring a rooftop solar potential heatmap (green = shadow-free solar zone, blue = shaded).
- G4. **One-Page Lead Summary**: Generate an executive lead qualification card with seasonal breakdown and confidence rating.
- G5. **One-Command Setup**: `docker compose up` starts healthy worker and n8n services ready for demo and automated execution.

**Non-Goals (MVP)**

- Internal roof obstructions (overhead water tanks, parapet walls, stair-head mumties, clotheslines) not captured in OSM footprints.
- Financial ROI / net-metering tariff calculation (disclosed as next step).
- Tree canopy and cloud-cover forecasting.

---

## 5. Rooftop Rating System (A–D)

Inspired by stakeholder proposals to the Ministry of New and Renewable Energy (MNRE):

| Grade | Criteria (Winter Dec 21 / Annual Benchmark) | Recommendation |
| --- | --- | --- |
| **Grade A (Prime Solar)** | $\ge 80\%$ of roof gets $\ge 4.5\text{ h}$ direct sun on Dec 21 | Highly recommended. Qualifies for maximum PM Surya Ghar capacity. |
| **Grade B (Good Solar)** | $60\%–79\%$ of roof gets $\ge 4.0\text{ h}$ direct sun on Dec 21 | Recommended. Suitable for 2–3 kW system on designated unshaded zone. |
| **Grade C (Marginal Solar)** | $40\%–59\%$ of roof gets $\ge 3.0\text{ h}$ direct sun on Dec 21 | Partial solar viable with elevated structure or East/West panel tilt. |
| **Grade D (Unviable / Heavy Shade)** | $< 40\%$ of roof gets $\ge 3.0\text{ h}$ direct sun on Dec 21 | **Disqualified**. Do not dispatch site visit. High shadow occlusion from neighbours. |

---

## 6. Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-1 | Accept a Telegram **location** message and locate the host building polygon from OpenStreetMap. |
| FR-2 | Discretize host rooftop into a regular grid (1.5 m spacing, $\approx 2.25\text{ m}^2$ per cell) at building height $Z = \text{height}$. |
| FR-3 | Ray-cast solar vectors for every roof grid cell at 5-minute intervals for Today, Dec 21, and Jun 21 against all surrounding 3D buildings within 300 m. |
| FR-4 | Count shadow-free hours per cell. Tag cells with $\ge 4.0\text{ h}$ direct sun in winter as **Usable Solar Area**. |
| FR-5 | Compute: Total Roof Area ($m^2$), Usable Roof Area ($m^2$), Usable Percentage, Suggested System Capacity ($\text{kWp} = \text{Usable Area} / 10$), and Rooftop Grade (A–D). |
| FR-6 | Render 3D Cycles-CPU time-lapse (MP4, H.264, 720×720) with rooftop cells colored by solar potential. |
| FR-7 | Deliver an instant Lead Qualification Summary message to Telegram. |
| FR-8 | Cache Overpass building queries (7-day SQLite cache) and full job results (24-hour cache). |
| FR-9 | Support `DEMO_FIXTURES=1` for offline demonstrations with realistic Indian urban building blocks. |

---

## 7. Honest Limitations & Disclosures

Every report and visual explicitly includes:
> **Installer Notice**: Major block shading from surrounding structures is modelled from OpenStreetMap. Rooftop micro-obstructions (overhead Sintex water tanks, parapet walls, stair-head mumties, and trees) are not mapped in OSM and must be verified during final physical site survey.
