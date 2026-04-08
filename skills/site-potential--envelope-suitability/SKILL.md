---
name: site-potential--envelope-suitability
description: Use when the architect wants to understand how much of their building envelope is physically available for BIPV installation. Reads CEA geometry and envelope property files to calculate usable opaque surface area, accounting for glazing, exclusion zones, and surface type. Also works in early design mode when window ratios are not yet defined.
intent: Translate building geometry and envelope properties into a clear picture of how much surface area is actually installable for BIPV — and in early design stages, tell the architect the maximum glazing they can have while still making BIPV viable.
type: component
position_in_tree: "Goal → Site Potential → Envelope Suitability"
---

## Purpose

Answer the question: **"How much of my building envelope is physically available for BIPV installation?"**

This skill reads building geometry and envelope property data from CEA4 to calculate the total opaque surface area available for BIPV across roof and facade orientations. It accounts for glazing (windows), and flags surfaces that are typically excluded from BIPV consideration.

**This skill operates in two modes:**

**Mode A — Defined envelope** (architect has already set window-to-wall ratios in CEA):
Calculates actual available opaque area per surface using the defined WWR values.

**Mode B — Early design stage** (window-to-wall ratios not yet defined):
Flips the question — calculates the maximum WWR the architect can apply to each facade while still keeping enough opaque area to justify BIPV installation. Gives the architect a design constraint to work with before committing to facade decisions.

---

## CEA4 Integration

This skill runs as a CEA4 plugin. All data is read automatically via the CEA4 `InputLocator`.

**Location context** read automatically from the project weather file:
```python
locator.get_weather()  # → .epw file containing city, latitude, longitude
```

**Building geometry** accessed via InputLocator:
```python
locator.get_zone_geometry()
# → zone.shp — building footprints, heights, floor counts
# Used to calculate: total facade area per orientation, roof area
```

**Envelope properties** accessed via InputLocator:
```python
locator.get_building_envelope_properties()
# → building-properties/envelope.csv
# Key columns: wwr_north, wwr_south, wwr_east, wwr_west
# (window-to-wall ratio per orientation, per building)
```

**Mode detection:** The skill checks whether `wwr_*` values are defined in `envelope.csv`. If all values are at the CEA default (0.4) or flagged as undefined, it switches to Mode B automatically and informs the architect.

---

## Data Sources

**Primary CEA files accessed via InputLocator:**

| File | What it provides |
|------|-----------------|
| `zone.shp` | Building footprint, height, number of floors → total facade and roof area |
| `building-properties/envelope.csv` | Window-to-wall ratio per orientation per building (`wwr_north`, `wwr_south`, `wwr_east`, `wwr_west`) |

**Key columns from `envelope.csv`:**
- `name` — building identifier
- `wwr_east`, `wwr_north`, `wwr_south`, `wwr_west` — window-to-wall ratio per facade orientation (0–1)

---

## Calculations

### Mode A — Defined envelope

**Step 1 — Calculate total facade area per orientation:**
```
facade_area_south = building_perimeter_south × building_height
(derived from zone.shp geometry)
```

**Step 2 — Calculate opaque area per facade:**
```
opaque_area_south = facade_area_south × (1 - wwr_south)
```

**Step 3 — Calculate roof area:**
```
roof_area = building_footprint_area
(from zone.shp)
```

**Step 4 — Calculate total installable area:**
```
total_installable = roof_area + sum(opaque_area per facade orientation)
```

**Step 5 — Calculate envelope installable fraction:**
```
installable_fraction = total_installable ÷ total_envelope_area
```

---

### Mode B — Early design stage

**Step 1 — Calculate minimum opaque area needed to justify BIPV:**
Using the radiation viability threshold (800 kWh/m²/year for facades) and a minimum viable panel size assumption (10m² minimum installation), calculate the minimum opaque area per facade that makes BIPV worthwhile.

**Step 2 — Calculate maximum WWR:**
```
max_wwr = 1 - (minimum_opaque_area ÷ total_facade_area)
```

**Step 3 — Output as design constraint:**
For each facade orientation: *"Your south facade can accommodate up to X% glazing and still support a meaningful BIPV installation."*

This gives the architect a concrete number to work with before finalising facade design.

---

## Scale Behaviour

**District scale:**
- Aggregates installable area across all buildings
- Framing: "Across the district, X m² of envelope is available for BIPV — Y% of the total envelope area"

**Cluster scale:**
- Compares installable fraction per building within the cluster
- Identifies which buildings have the most available envelope
- Framing: "Building B1000 has the highest installable fraction at X% — Building B1005 is most constrained at Y%"

**Building scale:**
- Shows installable area per surface for that specific building
- Framing: "For building B1000: roof = X m², south wall = Y m², east wall = Z m² available for BIPV"

---

## Benchmark

**Installable fraction interpretation:**
- > 60%: high availability — most of the envelope is usable
- 30–60%: moderate — selective placement, focus on priority surfaces
- < 30%: constrained — roof-only strategy likely most viable

**Typical WWR ranges in architecture:**
- Residential: 20–40% WWR typical
- Office / commercial: 40–70% WWR typical
- High glazing (curtain wall): > 70% — very limited opaque area for facade BIPV

**Maximum WWR for viable facade BIPV:**
As a general rule, facades with WWR > 70% rarely have enough opaque area to justify BIPV installation. The skill flags this threshold clearly in Mode B output.

---

## Surfaces Typically Excluded from BIPV

The skill flags the following surface types as typically non-installable, even if they are opaque:
- Balconies and railings
- Rooftop equipment zones (HVAC, technical units)
- Access and maintenance zones
- Highly fragmented or irregular surfaces
- Surfaces below 2m height (ground level — accessibility and safety)

These exclusions are applied as a percentage reduction to the calculated opaque area, based on standard BIPV practice assumptions. The LLM notes these assumptions clearly and flags that actual exclusions depend on the specific building design.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Total installable area broken down by surface (roof, south wall, east wall, west wall, north wall)
- WWR values per facade and what they mean for available area
- Installable fraction of total envelope
- Mode B: maximum WWR per facade as a design constraint with explanation

**Visualization:** Stacked bar chart per building or surface
- Shows total facade area split into: glazed (windows) / installable opaque / excluded opaque
- Makes the available fraction immediately visible
- Source data shown below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "X m² of your envelope is available for BIPV — concentrated on [surface]"
- Mode B: "To keep your south facade BIPV-viable, limit glazing to X%"
- One sentence on which surface offers the most opportunity

**Visualization:** Donut chart
- Segments: Roof / South wall / East wall / West wall / North wall / Excluded
- Shows relative contribution of each surface to total installable area

---

### If "Design implication" selected:
**What the LLM produces:**
- Concrete recommendation on where to focus BIPV installation
- Mode B: Specific WWR limits per facade as design guidelines
- If installable fraction is low: recommendation to prioritise roof and reconsider facade glazing strategy
- If installable fraction is high: confirmation that a comprehensive BIPV strategy is feasible
- Links to Surface Irradiation skill — combining available area with radiation data gives full picture of BIPV potential

**Visualization:** Envelope breakdown diagram
- Building elevation diagram showing: installable / glazed / excluded zones per facade
- Simple, schematic — designed to inform early design decisions

---

## Common Pitfalls

- **WWR is per orientation, not per building:** Each facade direction has its own WWR. A building with high south glazing may still have very usable north and east facades for BIPV — always break down by orientation.
- **Footprint ≠ roof area:** Some roofs have equipment, access zones, or irregular shapes that reduce installable area. The skill applies a standard 15% reduction to roof area to account for this unless more specific data is available.
- **Mode B is an estimate:** The maximum WWR calculation in early design mode is based on assumptions about minimum viable panel size. It should be used as a design guideline, not a precise limit. The skill always states this clearly.
- **Surroundings affect usable area:** Shading from neighbouring buildings (available in `surroundings.shp`) may further reduce the effective usable area. This skill does not account for shading — that is handled by the Contextual Shading skill.

---

## References

- CEA4 building geometry and envelope property documentation
- IDP 2024 Team 8: parametric study showing impact of surface exclusions on total installable area
- IDP 2025 Team 3: envelope analysis used to identify opaque vs glazed surfaces per orientation
- Interview — Interviewee A: "Confusion between facade areas, windows, and opaque surfaces was a common early misunderstanding"
- Interview — Interviewee C: "We focused on where PV actually makes sense — not just covering every surface"
