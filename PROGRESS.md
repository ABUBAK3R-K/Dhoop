# PROGRESS.md — Dhoop Solar: Rooftop Shade Qualifier Living Status

## Done
- **Documentation Updated for Dhoop Solar Commercial Pivot**:
  - `docs/prd.md` & `prd.md`: Solar installer qualification focus, PM Surya Ghar (1 crore households, ₹75,021 crore outlay), customer willingness to pay (₹50-100/lead vs ₹2,000 truck roll), Rooftop Grade A–D, usable roof area ($m^2$ / sq ft), suggested kWp capacity.
  - `docs/design.md` & `design.md`: Installer conversation UX, 3D rooftop solar potential heatmap (green/amber/navy), and Executive Solar Lead Qualification Card.
  - `docs/architecture.md` & `architecture.md`: Host rooftop polygon discretization (1.5 m grid cells), multi-point BVH ray-casting, unshaded area calculation ($\ge 4\text{ h}$ winter threshold), suggested kWp ($10\text{ m}^2/\text{kW}$), and `result.json` solar schema.
  - `docs/build_guide.md` & `build_guide.md`: Updated milestones M0–M6 for solar lead qualification.
  - `kickoff_prompt.md`: Updated kickoff brief for Dhoop Solar.

## Next
- Update core code modules (`geometry.py`, `blender_stage.py`, `report.py`, `pipeline.py`) to support rooftop grid generation and multi-point solar qualification metrics.
- Re-run `docker-compose build worker` (M0) to build the container runtime.
- Run checkpoint: verify `import bpy` and `ffmpeg` inside container.
- Run test suite: verify analytic wall shadow test, rooftop grid discretization, and solar metrics calculation.

## Decisions
- **Commercial Pivot**: Dhoop Solar qualifies rooftops for solar installers, EPCs, and solar loan lenders before committing to physical site visits.
- **Rooftop Grid**: 1.5 m cell discretization with 0.5 m edge inset over host building roof polygon.
- **Usable Solar Threshold**: $\ge 4.0\text{ h}$ shadow-free sunlight on winter solstice (Dec 21).
- **Suggested Capacity Formula**: $\text{kWp} = \text{round}(\text{Usable Area } (m^2) / 10.0, 1)$.
- **Rooftop Grade Scale**:
  - Grade A: $\ge 80\%$ unshaded ($\ge 4.5\text{ h}$ avg)
  - Grade B: $60\%–79\%$ unshaded ($\ge 4.0\text{ h}$ avg)
  - Grade C: $40\%–59\%$ unshaded ($\ge 3.0\text{ h}$ avg)
  - Grade D: $< 40\%$ unshaded (Disqualified lead)
- **Honest Disclosures**: OSM lacks rooftop water tanks (Sintex), parapets, and stair-head mumties; reports explicitly mandate a final site check for micro-obstructions.

## Open questions
- Grid resolution tuning: 1.5 m grid yields 20–60 points for standard 50–150 $m^2$ Indian residential roofs, keeping raycast execution under 100 ms.
