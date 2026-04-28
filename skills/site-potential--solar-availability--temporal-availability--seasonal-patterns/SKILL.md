---
name: site-potential--solar-availability--temporal-availability--seasonal-patterns
description: Use when the architect wants to understand long-term, season-to-season solar availability for BIPV. Reads CEA seasonal irradiation outputs and compares Spring, Summer, Autumn, and Winter performance by opaque surface.
intent: Show whether the BIPV strategy has a strong seasonal imbalance, which surfaces are most stable across the year, and whether long-term storage, grid dependency, or seasonal demand management should be considered.
type: component
position_in_tree: "Goal → Site Potential → Solar Availability → Temporal Availability → Seasonal Patterns"
---

## Purpose

Answer the question: **"How much does solar availability change across the year, and does the project face a long-term seasonal balancing problem?"**

This is the long-term temporal availability skill. It focuses on seasonal imbalance, not hour-of-day matching. It compares Spring, Summer, Autumn, and Winter irradiation by opaque surface and identifies whether winter output drops enough to create long-term grid dependency or seasonal storage pressure.

---

## Data Used

Primary files:
- `solar_irradiation_seasonally.csv`
- `solar_irradiation_seasonally_buildings.csv` when building or cluster selection is active

Columns:
- `period` for Spring / Summer / Autumn / Winter
- `irradiation_roof[kWh]`
- `irradiation_wall_south[kWh]`
- `irradiation_wall_east[kWh]`
- `irradiation_wall_west[kWh]`
- `irradiation_wall_north[kWh]`

Ignored:
- `irradiation_window_*`, because windows are not BIPV panel surfaces
- metadata columns such as `hour_start`, `hour_end`, `coverage_ratio`

---

## What Python Should Calculate

Do this before calling the LLM:

- seasonal total irradiation per opaque surface
- annual total per surface
- best and weakest season
- summer-to-winter ratio or max-season-to-min-season ratio
- surface with the most stable seasonal profile
- seasonal imbalance class:
  - low: ratio < 2
  - moderate: ratio 2-4
  - high: ratio > 4
- seasonal storage warning, if seasonal demand and PV generation are available

Do not ask the LLM to infer these values from raw CSV rows.

---

## LLM Role

The LLM should interpret the computed seasonal pattern:

- whether seasonal variation is mild, moderate, or strong
- whether winter output remains meaningful
- whether long-term storage is realistic at building scale
- whether seasonal imbalance should instead be handled through grid interaction, district infrastructure, thermal storage, or reduced winter self-sufficiency expectations
- which surfaces are more seasonally stable and why that matters

The LLM should not imply that seasonal battery storage is a normal room-sized design issue. Seasonal storage is usually a district or infrastructure-scale question unless a specific storage technology is provided.

---

## Output Expectations

**Key takeaway**
- Start with the strategy answer: whether the project has low, moderate, or high seasonal imbalance.
- State whether long-term storage is likely relevant, unrealistic at building scale, or not needed.
- Name the most stable surface or surface mix if it is available in the computed metrics.

**Explain the numbers**
- Explain seasonal totals, the summer/winter or max/min ratio, and what those values mean.
- Explain why total seasonal kWh changes: day length, sun angle, climate, and surface orientation.
- Connect the seasonal chart to grid dependency or seasonal self-sufficiency limits.

**Design implication**
- Translate the seasonal result into design strategy.
- If seasonal imbalance is high, avoid promising year-round independence from BIPV alone.
- If winter output is weak, frame BIPV as reducing annual grid demand while winter reliability comes from grid, district systems, or another storage concept.
- If a facade has a more stable profile, mention when it may be worth considering despite lower annual yield.

---

## Common Pitfalls

- Do not confuse seasonal storage with daily battery storage.
- Do not overpromise long-term storage from ordinary battery rooms.
- Do not describe high seasonal variation as a design failure; it is normal in many climates.
- Do not use window irradiation for BIPV panel recommendations.
- Do not ignore demand. Seasonal storage conclusions are strongest when seasonal demand and PV generation are both available.

## References

- CEA4 solar irradiation output documentation
- IDP 2025 Team 3: seasonal performance analysis used to evaluate facade orientation strategies
- IDP 2024 Team 2: seasonal demand-supply matching used to justify roof PV prioritisation
- Interview — Interviewee C: "We looked at production depending on orientation, time (daily/seasonal)"
