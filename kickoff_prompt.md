# Kickoff prompt — Dhoop Solar: Rooftop Shade Qualifier

Before starting: make sure `docs/prd.md`, `docs/design.md`, `docs/architecture.md`, and `docs/build_guide.md` exist in the repo.

---

```text
You are the lead engineer for "Dhoop Solar", an automated rooftop shade qualifier for solar installers and vendors.
A user sends a location pin on a building and gets back (1) a 3D rendered shadow time-lapse (MP4) with a rooftop solar heatmap, and (2) an executive Solar Lead Qualification Card with usable roof area (m² / sq ft), suggested capacity (kWp), Rooftop Grade (A–D), and shadow-free hours across seasons (Today, Dec 21, Jun 21).

Stack is fixed: n8n (orchestration & lead capture), Docker (runtime), Blender via `bpy` (Cycles CPU multi-point rooftop grid ray-casting + render). All three must be load-bearing.

Market & Purpose:
- Tailored for PM Surya Ghar: Muft Bijli Yojana (1 crore households, ₹75,021 crore outlay).
- Replaces expensive physical site visits (₹1,500–₹3,000 per lead) by qualifying usable shadow-free roof area remotely in 60 seconds.
- Rooftop Rating A–D matches MNRE stakeholder proposals on shadow-free hours.
- Honest limits: Water tanks, parapets and stair-heads are not in OSM; a site survey is still required before physical installation.

Key Technical Rules:
- Python 3.11 with `bpy~=4.5.0` inside the worker image.
- Render with Blender Cycles on CPU.
- Never import `bpy` in the FastAPI process; execute `python -m dhoop.blender_stage` as an isolated subprocess per job.
- Multi-point rooftop grid: discretize host roof polygon at 1.5 m spacing; raycast each cell against neighbouring building meshes.
- Compute usable unshaded area (cells >= 4h direct sun in winter Dec 21), suggested kWp (usable area / 10 m²), and Grade A–D.
- Maintain PROGRESS.md and execute milestone by milestone.
```
