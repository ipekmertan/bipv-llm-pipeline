---
name: site-potential--solar-availability--surface-irradiation
description: Use when the architect wants to know which parts of their building or district receive enough solar radiation to be worth covering with BIPV. Reads CEA solar irradiation outputs and compares surfaces by orientation and type.
intent: Translate raw CEA irradiation values (kWh per surface per year) into a clear ranking of which surfaces are most and least suitable for BIPV, with benchmarks and design-ready language. This is typically the first analysis an architect runs.
type: component
position_in_tree: "Goal → Site Potential → Solar Availability → Surface Irradiation"
---

## Purpose

Answer the question: **"Which parts of my building are worth covering with PV?"**

This skill reads CEA's solar irradiation output files and compares radiation received across all building surfaces (roof, and facade walls by orientation: N/S/E/W). It filters out windows (not installable), ranks opaque surfaces by annual irradiation received, and classifies each surface as usable, borderline, or exclude based on the standard BIPV radiation viability threshold.

This skill combines two analyses:
- **Surface irradiation** — how much radiation each surface receives
- **Usable solar fraction** — which surfaces cross the viability threshold and what percentage of the total envelope is viable

---

## CEA4 Integration

This skill runs as a CEA4 plugin. It does not require the user to upload or locate any files manually. All data is read automatically via the CEA4 `InputLocator` object, which knows the full project structure.

**Location context** is read automatically from the project's weather file:
```python
locator.get_weather()  # → path to .epw file, e.g. "Shanghai_2009.epw"
# The .epw file header contains latitude, longitude, and city name
# This is passed to the LLM for all contextual framing
```

**Building names** are read from the zone geometry:
```python
locator.get_zone_geometry()  # → zone.shp with all building names (e.g. B1000, B1001...)
```

**Solar irradiation data** is read from CEA4 outputs:
```python
locator.get_solar_radiation_csv()  # → solar_irradiation_annually.csv etc.
```

The user never needs to know where these files are. The plugin finds them automatically from the active CEA4 scenario.

---

## Data Sources

**Primary CEA files accessed via InputLocator:**

| Scale | File |
|-------|------|
| District | `solar_irradiation_annually.csv` |
| Cluster | `solar_irradiation_annually_buildings.csv` (filtered to named buildings) |
| Building | `solar_irradiation_annually_buildings.csv` (single building row) |

**Columns used (opaque surfaces only — windows excluded):**
- `irradiation_roof[kWh]`
- `irradiation_wall_north[kWh]`
- `irradiation_wall_south[kWh]`
- `irradiation_wall_east[kWh]`
- `irradiation_wall_west[kWh]`

**Columns ignored:**
- `irradiation_window_*` — windows cannot have BIPV installed
- `hour_start`, `hour_end`, `nominal_hours`, `coverage_ratio` — metadata only

---

## Scale Behaviour

**District scale:**
- Uses `solar_irradiation_annually.csv` (1 row = whole district aggregate)
- Computes total kWh per surface type across district
- Framing: "Across the district, roof receives X times more radiation than north facades"

**Cluster scale:**
- Uses `solar_irradiation_annually_buildings.csv`, filtered to the named buildings
- Computes average and total per surface across the cluster
- Framing: "Across buildings [B1, B2, B3], south walls consistently outperform north walls"

**Building scale:**
- Uses `solar_irradiation_annually_buildings.csv`, single building row
- Shows surface-by-surface breakdown for that building
- Framing: "For building B1000, the roof receives X kWh/year — significantly above the viability threshold"

---

## Threshold Calculation (Usable Solar Fraction)

Applied on top of the irradiation values to classify each surface:

**Thresholds:**

| Surface | Threshold |
|---------|-----------|
| Roof | 1,000 kWh/m²/year |
| Facade walls (all orientations) | 800 kWh/m²/year |

**Classification:**
- **Usable ✓** — irradiation per m² is above threshold
- **Borderline ~** — irradiation per m² is within 20% below threshold
- **Exclude ✗** — irradiation per m² is more than 20% below threshold

**Usable fraction:**
```
Usable fraction = sum of usable surface area ÷ total available surface area
```

**Important:** CEA outputs total kWh, not kWh/m². Surface area is read from the building geometry file (`zone.shp`) via the InputLocator to convert units. If unavailable, the skill uses relative surface comparisons and flags the limitation.

**CEA threshold parameter:** CEA has a built-in radiation threshold (default = 800 kWh/m²/year). This skill reads that value from the CEA project config and uses it — respecting any changes the user has made to the default.

---



The standard radiation viability threshold used in BIPV practice is **800 kWh/m²/year** for facades, **1000 kWh/m²/year** for roofs.

Note: CEA outputs total kWh (not kWh/m²). To apply benchmarks, divide by the surface area. If surface area is not available from CEA at this stage, the LLM uses relative comparisons between surfaces instead, and flags this limitation clearly.

**Orientation benchmarks for Shanghai context (from IDP project data):**
- Roof: highest — typically dominates all facade orientations
- South wall: second best
- East / West wall: moderate — useful for morning/evening load matching
- North wall: lowest — rarely worth installing

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- A plain-language explanation of each surface value
- Comparison against the 800/1000 kWh/m²/year threshold
- Clear classification label for each surface: Usable ✓ / Borderline ~ / Exclude ✗
- The overall usable fraction percentage of the total envelope
- Note on what windows are excluded and why
- Note on the CEA threshold parameter value used

**Visualization:** Grouped horizontal bar chart with classification
- X axis: irradiation (kWh)
- Bars: one per surface (roof, wall_south, wall_east, wall_west, wall_north)
- Colour: green if usable, amber if borderline, red if exclude
- Threshold line marked on chart
- Usable fraction % shown as summary below chart
- Source data shown below chart

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your roof dominates — it receives X times more radiation than your best facade"
- One supporting sentence on the second-best surface
- One sentence flagging the worst surface and why it can likely be excluded

**Visualization:** Ranked bar chart (surfaces ordered highest to lowest)
- Highlights the top surface in a distinct colour
- Minimal labels — designed to be readable in a presentation

---

### If "Design implication" selected:
**What the LLM produces:**
- Prioritised surface list: Primary / Secondary / Exclude
- The usable fraction percentage and what it means for BIPV strategy:
  - > 60%: comprehensive BIPV strategy is viable
  - 30–60%: selective placement recommended, focus on priority surfaces
  - < 30%: roof-only strategy recommended, facade BIPV likely not cost-effective
- Concrete recommendation: "Prioritise roof coverage first. If facade BIPV is desired for architectural reasons, focus on south and east orientations."
- Notes any context-specific factors (e.g. if east/west perform unusually well, flag load-matching opportunity — links to Demand vs Supply skill)
- Flags surfaces to exclude from BIPV consideration

**Visualization:** Surface priority diagram
- Simple ranking: Primary ✓ / Secondary ~ / Exclude ✗
- One row per surface with label, value, and classification
- Usable fraction % shown as summary
- Designed to be copied directly into a design report

---

## Common Pitfalls

- **Windows included in total:** CEA outputs window irradiation separately — always exclude `irradiation_window_*` columns. Including windows inflates facade values and misleads panel placement decisions.
- **Total kWh vs kWh/m²:** CEA gives total kWh, not intensity. A large north wall can show higher total kWh than a small south wall even though it is less efficient per m². Always convert to kWh/m² before applying thresholds and note this distinction in the output.
- **Threshold sensitivity:** Small changes to the radiation threshold parameter significantly affect how many surfaces are classified as usable. Always display the threshold value used and flag if it differs from the default 800/1000 kWh/m²/year.
- **Shading already accounted for:** CEA irradiation values already include shading from surrounding buildings. The usable fraction therefore reflects actual shaded conditions — architects may expect higher values if they are thinking of unobstructed surfaces.
- **Roof dominance is expected:** In all Shanghai IDP case studies reviewed, roof consistently outperformed all facades. Do not flag this as surprising — frame it as confirmation of expected solar logic.

---

## References

- CEA4 solar irradiation output documentation
- IDP 2025 Team 3: facade orientation study showing E/W advantage
- IDP 2024 Team 8: radiation threshold parametric study, threshold = 1000 kWh/m²/year used as baseline
- IDP 2024 Team 2: finding that roof dominates over facade yield in all scenarios
- Interview — Interviewee A: iterative use of solar irradiation simulations to evaluate building orientations
- Interview — Interviewee B: roof consistently outperforms facade surfaces
