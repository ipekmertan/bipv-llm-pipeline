---
name: site-potential--solar-availability--temporal-availability--storage-strategy
description: Use when the architect wants to know whether short-term and/or long-term storage is necessary for BIPV. Combines daily timing, seasonal imbalance, PV generation, demand, use type, and envelope constraints to estimate storage implications and design strategy.
intent: Decide whether the project needs short-term storage, long-term storage, both, or mainly grid interaction, and translate that into BIPV surface mix, approximate battery-room allowance, and architectural design implications.
type: component
position_in_tree: "Goal → Site Potential → Solar Availability → Temporal Availability → Storage Necessity"
---

## Purpose

Answer the question: **"Does this project need short-term or seasonal storage, and what does that imply for BIPV design?"**

This is the combined temporal insight skill. It should synthesize the daily and seasonal patterns into a strategy answer:

- which combination of surfaces gives the most constant useful solar profile
- whether short-term storage is needed for daily mismatch
- whether long-term or seasonal storage is relevant
- how much battery capacity and technical-room area may be needed, if hourly PV generation and demand are available
- how building use type and WWR affect the design recommendation

---

## Data Used

Use only files that are available in the uploaded CEA project:

Daily timing:
- `solar_irradiation_hourly.csv`

Seasonal timing:
- `solar_irradiation_seasonally.csv`
- `solar_irradiation_seasonally_buildings.csv`

PV generation:
- `PV_PV1_total.csv`, `PV_PV2_total.csv`, `PV_PV3_total.csv`, `PV_PV4_total.csv`
- `PV_PV1_total_buildings.csv`, etc.

Demand:
- `Total_demand_hourly.csv`
- individual building demand files such as `B1000.csv`
- `demand_seasonally.csv` or `Total_demand.csv` when hourly demand is not available

Envelope and use type:
- `envelope.csv` for WWR by orientation
- `zone.dbf` or `typology.dbf` for building use type mix
- use-type parameter table if present in the CEA database

Panel parameters:
- `PHOTOVOLTAIC_PANELS.csv`

---

## What Python Should Calculate

Do this before calling the LLM:

**Daily profile**
- average 24-hour irradiation profile by surface
- peak hour by surface
- best morning, midday, and afternoon surfaces
- smoothest viable surface combination

**Seasonal profile**
- seasonal total by surface
- max/min seasonal ratio
- most seasonally stable surface
- seasonal imbalance class

**Storage sizing**
If hourly PV generation and hourly demand are available:
- hourly demand
- hourly PV generation for the selected panel type
- hourly surplus and deficit
- daily short-term storage need, in kWh
- annual or seasonal mismatch indicator
- approximate battery-room area

Recommended early-stage battery-room planning formula:
```
battery_room_m2 = battery_capacity_kWh / 150
```

This is a conservative technical-room allowance for racks, clearance, access, ventilation, and safety spacing. It is not an engineering specification.

**Envelope/use type**
- dominant building use type and use-type mix
- likely occupancy timing, if use-type parameters are available
- WWR per orientation
- PV surface coverage already simulated by orientation
- potential facade coverage constraints from WWR, if geometry and envelope data allow it

---

## LLM Role

The LLM should interpret the computed metrics into an architectural strategy:

- give the strategy answer first
- explain which surface mix creates the most constant solar profile
- explain whether daily storage, seasonal storage, both, or mainly grid interaction is needed
- explain where storage could fit in the building context
- adapt recommendations to use type and likely occupancy timing
- explain how WWR affects facade PV coverage feasibility

Do not invent missing electricity prices, regulations, tariffs, storage products, or detailed engineering requirements.

---

## Output Expectations

**Key takeaway**
- Start with the strategy answer, not the data explanation.
- State the recommended surface mix.
- State storage category:
  - no storage priority
  - short-term battery storage recommended
  - seasonal storage/grid dependency issue
  - both short-term and long-term balancing needed
- If hourly demand and PV are available, give approximate battery capacity and battery-room area.
- Mention likely building location for the storage room, such as basement/service room/electrical room/roof plant room, based on project context if available.

**Explain the numbers**
- Explain daily timing numbers, seasonal imbalance numbers, and storage calculation logic.
- Explain the chart and why the proposed surface mix smooths the profile.
- Show the reasoning behind the storage category.
- Clearly state limitations, especially if storage is estimated from PV/demand rather than engineered system design.

**Design implication**
- Use building use type to interpret design flexibility and occupied-use times.
- Recommend approximate PV coverage percentages for the surfaces named in the strategy, only if WWR/area/PV data are available.
- Explain how the coverage could be achieved with the project's WWR and facade constraints.
- Distinguish roof coverage, facade coverage, and storage-room allowance as separate design moves.
- For residential or evening-heavy uses, emphasize storage or shared/community energy use.
- For office, school, retail, hospital, or industrial daytime-heavy uses, emphasize direct self-consumption and daily load matching.

---

## Common Pitfalls

- Do not size storage from irradiation alone. Use hourly PV generation and hourly demand.
- Do not treat seasonal storage as a normal battery-room issue. Seasonal storage is usually district-scale, grid-based, thermal, hydrogen, or other specialized infrastructure.
- Do not recommend facade PV coverage percentages unless envelope/WWR and area data support the claim.
- Do not assume roof-only PV is the final design if wall panels were excluded from the PV simulation. If walls were excluded, say that facade recommendations are based on irradiation potential and require re-running PV with wall panels enabled.
- Do not use one default panel value for all PV types. Panel parameters must come from `PHOTOVOLTAIC_PANELS.csv`.
