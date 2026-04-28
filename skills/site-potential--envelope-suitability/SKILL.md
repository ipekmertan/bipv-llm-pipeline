---
name: site-potential--envelope-suitability
description: Use when the architect needs to know which envelope surfaces are actually suitable for BIPV after combining solar potential, surface availability, WWR, accessibility, visibility, and design trade-offs.
intent: Produce a surface-by-surface suitability matrix and translate it into BIPV integration opportunities and conflict flags.
type: component
position_in_tree: "Goal -> Site Potential -> Envelope Suitability"
---

## Purpose

Answer the question: **"Which parts of the envelope are suitable for BIPV, and what trade-offs should the architect notice?"**

This is a synthesis node. It must not only rank irradiation. It combines:

- solar potential from irradiation outputs
- surface area or simulated PV area when available
- WWR / facade continuity from `envelope.csv`
- accessibility for installation and maintenance
- visibility / architectural prominence
- conflict flags where one criterion pushes against another

The goal is to help the architect notice design opportunities and negotiation points that are easy to miss when looking only at radiation.

---

## Data Used

Primary:
- `solar_irradiation_annually.csv`
- `solar_irradiation_annually_buildings.csv`
- `envelope.csv`
- `PV_PV*_total_buildings.csv` when simulated PV area is available

Useful columns:
- `irradiation_roof[kWh]`
- `irradiation_wall_south[kWh]`
- `irradiation_wall_east[kWh]`
- `irradiation_wall_west[kWh]`
- `irradiation_wall_north[kWh]`
- `wwr_south`, `wwr_east`, `wwr_west`, `wwr_north`
- `PV_roofs_top_m2`
- `PV_walls_south_m2`, `PV_walls_east_m2`, `PV_walls_west_m2`, `PV_walls_north_m2`

Ignored:
- window irradiation columns for BIPV recommendations
- generic facade advice not connected to the computed matrix

---

## What Python Should Calculate

Before calling the LLM, calculate a compact suitability matrix:

- annual irradiation per opaque surface
- share of total opaque-surface irradiation
- WWR per facade, if available
- simulated PV area per surface, if available
- accessibility class:
  - roof: usually reachable, but may conflict with access paths or equipment
  - facade: requires vertical access and maintenance planning
- visibility class:
  - roof: usually low visibility / lower aesthetic constraint
  - facades: high visibility / architectural expression issue
- suitability class:
  - HIGH: strong solar potential plus usable/continuous surface
  - MEDIUM: useful but selective or constrained
  - LOW: weak solar potential, fragmented area, or low simulated area
- conflict flags visible in the data

Do not ask the LLM to calculate these from raw CSV rows.

---

## LLM Role

Use the computed matrix to interpret trade-offs.

The LLM should:

- state which surfaces are HIGH / MEDIUM / LOW suitability
- identify "free" surfaces: good potential with low visibility, usually roof
- identify architectural opportunity surfaces: good potential with high visibility, usually prominent facades
- for high-visibility suitable facades, name relevant BIPV product/design options the architect can look up
- flag conflicts:
  - high solar potential but zero simulated PV area
  - high WWR limiting facade integration
  - high-potential roof that may need coordination with roof access/equipment if that is visible in the data
- avoid repeating the same point in different wording
- avoid generic claims like "south is best" unless the computed data supports it

The LLM must not invent design-intent conflicts. If rooftop terrace, heritage, equipment zones, facade articulation, or client priorities are not provided, do not pretend they are known.

---

## Output Expectations

**Key takeaway**
- Start with the main suitability answer.
- Name the best surface and why, using one or two decisive numbers.
- Mention the main trade-off only if it changes the design decision.
- End with the BIPV move: full integration, selective integration, roof-first, facade-feature, or avoid PV.

**Explain the numbers**
- Give the surface-by-surface matrix.
- For each surface, include: irradiation, WWR or simulated area if available, suitability class, and the reason for that class.
- Explain only numbers that affect the suitability decision.
- Do not repeat the same orientation logic after every row.

**Design implication**
- Turn the matrix into design actions.
- Distinguish:
  - low-visibility technical opportunity
  - high-visibility architectural opportunity, with searchable BIPV option names
  - surfaces better left as conventional cladding
- Include conflict flags as negotiation points, not failures.
- If data is missing, say exactly what is missing and avoid filling it with invented project facts.
- When a visible facade has HIGH or MEDIUM suitability, give 2-4 relevant BIPV option names from the computed metrics. Do not list every option if only one or two fit the surface.

---

## Tone and Redundancy Rules

- Be concise but not shallow.
- Do not add introductions like "this analysis considers..." when the answer can start with the result.
- Do not restate the same surface ranking in every paragraph.
- Do not describe charts.
- Do not include methodology unless the user selected Explain the numbers and the method affects interpretation.
- Use direct architectural language: "use", "avoid", "reserve", "treat as", "coordinate with".

---

## Example Logic

If the roof has high irradiation and low visibility:
- "Roof: HIGH suitability. It is the least aesthetically constrained BIPV surface, so use it as the baseline PV area before negotiating facade expression."

If the south facade has high irradiation and high visibility:
- "South wall: HIGH suitability, but visually prominent. Treat BIPV here as facade design, not hidden infrastructure. Look up opaque BIPV facade cladding, colored or patterned BIPV modules, or PV shading devices depending on the facade language."

If the north facade has low irradiation and fragmented/limited area:
- "North wall: LOW suitability. Use conventional cladding unless there is a non-energy reason to use BIPV."

If the data shows a conflict:
- "Conflict: the south wall has meaningful irradiation but zero simulated PV area. Check whether facade PV was excluded from the simulation before treating the facade as unsuitable."

## References

- CEA4 building geometry and envelope property documentation
- IDP 2024 Team 8: parametric study showing impact of surface exclusions on total installable area
- IDP 2025 Team 3: envelope analysis used to identify opaque vs glazed surfaces per orientation
- Interview — Interviewee A: "Confusion between facade areas, windows, and opaque surfaces was a common early misunderstanding"
- Interview — Interviewee C: "We focused on where PV actually makes sense — not just covering every surface"
