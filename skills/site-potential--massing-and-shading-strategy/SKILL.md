---
name: site-potential--massing-and-shading-strategy
description: Use when the architect wants to understand how surrounding context affects solar access across their project, and how massing or positioning decisions can maximise BIPV potential. Reads CEA surroundings geometry and irradiation data to identify shading-constrained buildings and surfaces, and provides early design guidance on massing strategy.
intent: Move beyond reporting shading as a problem and instead use it as a design input — identifying which buildings or surfaces are most constrained by context, which are least affected, and what massing or spacing decisions would improve solar access for BIPV.
type: component
position_in_tree: "Goal → Site Potential → Massing & Shading Strategy"
---

## Purpose

Answer the question: **"How does the surrounding context affect solar access across my project, and what massing decisions would improve BIPV potential?"**

This skill uses CEA's surroundings geometry data combined with irradiation results to understand the shadow-casting context of the project. It operates at two levels:

- **Analysis** — which buildings or surfaces are most affected by neighbouring context
- **Early design guidance** — what massing, spacing, or orientation decisions would reduce shading and maximise BIPV potential

**Important note on how shading works in CEA:**
CEA does not produce a separate shading output file. Instead, shading from surrounding buildings is already embedded in the irradiation values — when CEA calculates solar irradiation per surface, it uses `surroundings.shp` to cast shadows. This means surfaces performing lower than expected for their orientation are likely shading-constrained. This skill makes that relationship visible and actionable.

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.

## Data Sources

**Primary CEA files accessed via InputLocator:**

| File | What it provides |
|------|-----------------|
| `surroundings.shp` | Neighbouring building footprints and heights |
| `zone.shp` | Project building footprints and heights |
| `solar_irradiation_annually_buildings.csv` | Actual irradiation per building — used to identify underperformers |

---

## Analysis Logic

**Step 1 — Identify shading-constrained buildings:**
Compare each project building's irradiation values against the expected range for its orientation and climate zone. Buildings significantly below expected values are flagged as potentially shading-constrained.

**Step 2 — Identify shadow-casting neighbours:**
For each flagged building, check `surroundings.shp` for neighbouring structures that are:
- Taller than the project building, or
- Within a critical distance (approximately 2× the neighbour's height to the south in northern hemisphere, 2× to the north in southern hemisphere)

**Step 3 — Calculate shading impact estimate:**
```
shading_impact = (expected_irradiation - actual_irradiation) ÷ expected_irradiation × 100%
```
This gives an approximate percentage of irradiation lost to shading per building.

**Step 4 — Early design mode:**
If the architect has not yet finalised massing, the skill uses surroundings data to suggest:
- Minimum building spacing to avoid mutual shading
- Optimal building height relative to neighbours for maximum solar access
- Which parts of the site are most sheltered vs most exposed to shading

---

## Scale Behaviour

**District scale:**
- Ranks all buildings by shading impact — from least to most constrained
- Identifies which buildings are poor BIPV candidates due to context
- Identifies which buildings have clear solar access and are strong BIPV candidates
- Framing: "Buildings B1000, B1003, B1007 have the least shading impact and are your strongest BIPV investment opportunities. Buildings B1012 and B1014 are heavily constrained by neighbouring structures."

**Cluster scale:**
- Focuses on mutual shading within the cluster — do the cluster's own buildings shade each other?
- Flags north-facing surfaces of taller buildings casting shadows on shorter neighbours
- Framing: "Within your cluster, B1005 casts significant shadow on B1004's south facade — consider height adjustment or spacing increase"

**Building scale:**
- Identifies which specific facades are most affected by neighbouring context
- Early design mode: provides massing guidance — height, setback, orientation recommendations
- Framing: "Your east facade receives X% less irradiation than expected — the adjacent 8-storey building to the east is the likely cause. Increasing setback by Y metres would recover approximately Z% of lost irradiation."

---

## Early Design Mode

When the architect is still defining massing (building heights, footprints, spacing not yet finalised), this skill switches to generative guidance mode:

**District scale early design:**
*"Based on the surrounding context, which plots on this site have the strongest solar access for BIPV investment?"*
- Maps shadow-casting neighbours onto the site
- Identifies zones of high and low solar exposure
- Recommends which plots to prioritise for BIPV-intensive buildings

**Building scale early design:**
*"What massing decisions would minimise shading and maximise BIPV potential for this building?"*
- Calculates minimum height to avoid being shaded by immediate neighbours
- Calculates maximum height before the building starts shading itself (self-shading on lower floors)
- Recommends optimal orientation relative to tallest neighbours
- Provides specific setback distances for meaningful solar access improvement

---

## Benchmark

**Shading impact thresholds:**
- < 10% irradiation loss: low shading impact — context is not a significant constraint
- 10–30% loss: moderate — worth considering in BIPV placement decisions
- > 30% loss: high — context significantly constrains BIPV viability on affected surfaces

**Critical shadow distance (approximate rule of thumb):**
- For a neighbouring building of height H: significant shading occurs within a distance of 2H to the south (northern hemisphere) or 2H to the north (southern hemisphere)
- The LLM reads the project latitude from the weather file to determine which hemisphere applies

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Shading impact estimate per building (% irradiation loss vs expected)
- Identification of main shadow-casting neighbours with their height and distance
- Plain-language explanation of how CEA embeds shading into irradiation values

**Visualization:** District map with shading impact overlay
- Buildings colour-coded by shading impact: green (low) → amber (moderate) → red (high)
- Shadow-casting neighbours highlighted
- Source data shown below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline identifying the most and least shading-constrained buildings
- One sentence on the dominant shadow source in the project
- One sentence on early design implication

**Visualization:** Ranked bar chart
- Buildings ordered by shading impact (lowest to highest)
- Makes BIPV investment priority immediately visible at district scale

---

### If "Design implication" selected:
**What the LLM produces:**
- Clear BIPV investment priority list based on shading context
- Early design massing recommendations (setback, height, orientation) where applicable
- Specific buildings or surfaces to deprioritise for BIPV due to context constraints
- Links to Surface Irradiation skill — combining shading context with irradiation data gives full picture

**Visualization:** Massing strategy diagram
- Schematic showing shadow-casting relationships
- Recommended setback distances and height relationships
- Designed to be used directly in early design presentations

---

## Common Pitfalls

- **Shading is already in irradiation values:** Never double-count shading. The irradiation values from CEA already include it. This skill explains and contextualises the shading impact — it does not apply additional reductions.
- **Surroundings.shp may be incomplete:** The surroundings file contains only the buildings that were included when the CEA project was set up. If neighbouring buildings are missing, shading will be underestimated. Always flag this limitation.
- **Trees and vegetation:** CEA's surroundings file contains buildings only — not trees or other vegetation. In contexts with significant tree cover, actual shading will be higher than calculated. The skill flags this when the location context suggests significant vegetation (e.g. suburban or park-adjacent sites).
- **Early design estimates are approximate:** Massing recommendations in early design mode are based on geometric shadow calculations, not full radiation simulation. They should be used as design guidelines, validated by running CEA simulation once massing is defined.

---

## References

- CEA4 surroundings geometry documentation
- IDP 2025 Team 3: building orientation and massing study showing impact of neighbouring context on facade irradiation
- IDP 2024 Team 2: solar fraction analysis revealing shading as key factor in low-performing facades
- Interview — Interviewee A: iterative massing adjustments based on solar simulation results
- Interview — Interviewee C: district-level analysis used to identify which buildings to prioritise for energy intervention

---

## PV Simulation Config — Design Implications

The app injects the following inferred parameters from the CEA output into your context:

```
panel-on-roof: YES/NO
panel-on-wall: YES/NO
Panel types simulated: PV1, PV2, ...
```

**Use these to proactively flag design implications:**

- If `panel-on-wall: NO` → *"Your simulation excluded wall surfaces. Facade BIPV is often the most architecturally integrated option — consider enabling walls and re-running."*
- If `panel-on-roof: NO` → *"Roof surfaces were excluded. These typically receive the highest irradiation and lowest shading — worth including for a complete picture."*
- If only 1 panel type was simulated → *"Only PV1 was simulated. Running all 4 types would show whether a lower-embodied-carbon panel (e.g. CdTe) could justify more surfaces."*
