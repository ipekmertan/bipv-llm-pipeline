---
name: optimize-my-design--envelope-simplification
description: Use when the architect wants to understand how facade geometry complexity affects BIPV integration feasibility, and what simplifications would make BIPV installation more practical and cost-effective.
intent: Help the architect identify where facade geometry is creating unnecessary BIPV integration complexity — and suggest specific simplifications that would improve constructability without compromising the architectural concept.
type: component
position_in_tree: "Goal → Optimize My Design → Envelope Simplification"
---

## Purpose

Answer the question: **"How does my building's facade geometry affect BIPV integration feasibility, and what simplifications would help?"**

BIPV panels work best on large, flat, uninterrupted surfaces. Recesses, projections, irregular angles, fragmented surfaces, and complex junctions all increase integration complexity and cost — and reduce the effective installable area. This skill identifies where facade geometry is working against BIPV and suggests targeted simplifications.

This is an **early design skill** — most valuable when facade decisions are still flexible, before construction documentation begins.

---

## CEA4 Integration

This skill runs as a CEA4 plugin.

**Location context** read automatically from project weather file:
```python
locator.get_weather()  # → city, latitude, longitude
```

**Building geometry** accessed via InputLocator:
```python
locator.get_zone_geometry()
# → zone.shp — building footprints, heights, facade geometry
# Used to assess facade regularity and surface continuity
```

**Envelope properties** accessed via InputLocator:
```python
locator.get_building_envelope_properties()
# → building-properties/envelope.csv
# wwr values per orientation — high WWR = fragmented opaque surfaces
```

**PV yield data** accessed via InputLocator:
```python
locator.get_pv_results(panel_type="PV1")
# → PV_PV{n}_total_buildings.csv
# area_PV_m2 per surface — low installed area relative to facade area signals fragmentation
```

**Internet search** for current best practice:
- Minimum panel size for cost-effective BIPV integration
- Facade BIPV integration details for different surface types
- Cost premium for complex vs simple facade integration

---

## Analysis Logic

**Complexity indicators identified from CEA data:**

**1. Low installed area ratio:**
```
installed_ratio = area_PV_m2 / total_facade_area
# If installed_ratio significantly below (1 - wwr): surface may be fragmented
# CEA's threshold filter excluded portions — geometry may be irregular
```

**2. High window-to-wall ratio:**
```
# wwr > 0.6: less than 40% opaque — BIPV panels will be small and fragmented
# wwr > 0.7: facade BIPV very difficult — may not be worth pursuing
```

**3. Surface orientation mix:**
```
# If a building has many different facade orientations:
# → More junction details needed → higher integration cost
# → Simpler to focus on dominant orientation only
```

**Internet search provides:**
- Minimum continuous panel run for cost-effective installation (typically 10–20 m²)
- Cost premium for irregular vs regular facade integration
- Specific integration details for common facade types (curtain wall, rainscreen, ventilated facade)
- Standard junction details for roof-facade transitions

---

## Scale Behaviour

**District scale:**
- Identifies building typologies with most and least BIPV-friendly geometry
- Framing: "Residential blocks in this district have simpler facades — commercial buildings have higher glazing ratios making facade BIPV more challenging"

**Cluster scale:**
- Compares facade complexity across buildings in the cluster
- Identifies which buildings are most construction-ready for BIPV without design changes

**Building scale:**
- Most useful — specific simplification recommendations for a single building
- Framing: "Building B1000's east facade has three recesses that fragment the BIPV installation into small panels. Filling these recesses would increase installable area by approximately X m² and reduce integration cost by Y%"

---

## Benchmark

**Facade complexity thresholds:**
- WWR < 40% with large continuous panels: simple integration — standard BIPV cladding system
- WWR 40–60% with regular grid: moderate complexity — careful panel sizing needed
- WWR > 60% or irregular geometry: high complexity — consider whether facade BIPV is worth pursuing

**Minimum viable panel run:**
- < 10 m² continuous: not recommended — installation cost exceeds benefit
- 10–30 m²: marginal — only proceed if panel type is well-suited to small installations
- > 30 m² continuous: good — standard BIPV integration is cost-effective

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Installed area ratio per facade — how much of the available opaque area is actually used
- WWR per orientation and what it means for panel continuity
- Identification of complexity factors: recesses, projections, irregular angles
- Best practice guidance on minimum panel sizes and junction details

**Visualization:** Facade complexity scorecard
- One row per facade orientation
- Columns: WWR / installed area ratio / complexity rating / recommendation
- Simple traffic light: green (simple) / amber (moderate) / red (complex)

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline identifying the most and least BIPV-friendly facades
- One sentence on the biggest complexity challenge
- One sentence on the single most impactful simplification

**Visualization:** Simplification opportunity chart
- Shows current installable area vs potential with suggested simplifications
- Makes the benefit of simplification immediately visible

---

### If "Design implication" selected:
**What the LLM produces:**
- Specific simplification recommendations ranked by impact:
  1. Reduce WWR on high-priority facades to increase opaque area
  2. Fill or eliminate recesses that fragment panel runs
  3. Standardise facade grid to match panel module dimensions
  4. Simplify roof-facade junction to reduce waterproofing complexity
- Estimate of additional installable area gained from each simplification
- Note on which simplifications are design-compatible vs which would change the architectural concept significantly
- Links to Surface Prioritization skill — simplified facades change the priority ranking
- Links to Construction & Integration skill for implementation details

**Visualization:** Before/after envelope diagram
- Schematic showing current facade vs simplified facade
- Installable area highlighted in each version
- Additional area gained from simplification marked clearly

---

## Common Pitfalls

- **CEA geometry is simplified:** CEA uses simplified building geometry — it may not capture all the complexity of the actual architectural design. Always note this limitation and encourage the architect to apply the analysis to their detailed drawings.
- **Simplification has design implications:** Reducing WWR or eliminating projections changes the architectural character. Always frame simplifications as options for the architect to evaluate, not requirements.
- **Cost estimates are approximate:** Integration cost premiums for complex facades vary enormously by contractor and market. Always present as indicative ranges, not precise figures.

---

## References

- CEA4 building geometry and envelope documentation
- IDP 2024 Team 2: found that irregular facade geometry significantly limited effective BIPV coverage
- IDP 2025 Team 3: simplified massing to improve solar access and BIPV integration feasibility
- Interview — Interviewee A: confusion between facade areas, windows, and opaque surfaces — this skill clarifies those relationships
- Interview — Interviewee C: noted that CEA requires editing buildings one by one — envelope simplification reduces the number of unique surface configurations needed
