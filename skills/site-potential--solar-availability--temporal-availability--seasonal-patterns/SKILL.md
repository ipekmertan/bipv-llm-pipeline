---
name: site-potential--solar-availability--temporal-availability--seasonal-patterns
description: Use when the architect wants to understand how solar availability changes across seasons. Reads CEA seasonal irradiation outputs and compares Spring, Summer, Autumn, Winter performance to identify when BIPV is most and least productive.
intent: Translate CEA's seasonal irradiation breakdown into design-relevant insight about when the building's BIPV system performs, when it underperforms, and what that means for energy strategy decisions.
type: component
position_in_tree: "Goal → Site Potential → Solar Availability → Temporal Availability → Seasonal Patterns"
---

## Purpose

Answer the question: **"When during the year does my building receive the most solar energy, and how much does it drop in winter?"**

This skill reads CEA's seasonal irradiation output and compares radiation across the four seasons for all opaque surfaces. It identifies peak and low seasons, the ratio between them, and frames the result in terms of what it means for BIPV energy strategy.

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.
## Data Sources

| Cluster | `solar_irradiation_seasonally_buildings.csv` (filtered to named buildings) |
| Building | `solar_irradiation_seasonally_buildings.csv` (single building, 4 rows) |

**Columns used (opaque surfaces only):**
- `period` — Spring / Summer / Autumn / Winter
- `irradiation_roof[kWh]`
- `irradiation_wall_north[kWh]`
- `irradiation_wall_south[kWh]`
- `irradiation_wall_east[kWh]`
- `irradiation_wall_west[kWh]`

**Columns ignored:**
- `irradiation_window_*` — windows cannot have BIPV installed
- `hour_start`, `hour_end`, `nominal_hours`, `coverage_ratio` — metadata only

**Key data observed (from case study):**
- 4 rows per file at district level: Spring, Summer, Autumn, Winter
- 4 rows per building at building level (one per season)
- Summer dominates significantly — roof Summer ≈ 4.8× Winter in this dataset

---

## Scale Behaviour

**District scale:**
- Uses `solar_irradiation_seasonally.csv` (4 rows = 4 seasons, whole district)
- Computes seasonal totals across all surfaces
- Framing: "District-wide, Summer generates X times more solar energy than Winter"

**Cluster scale:**
- Uses `solar_irradiation_seasonally_buildings.csv`, filtered to named buildings
- Averages seasonal values across the cluster
- Framing: "Across buildings [B1, B2, B3], the Summer-to-Winter ratio averages X"

**Building scale:**
- Uses `solar_irradiation_seasonally_buildings.csv`, single building (4 rows)
- Shows season-by-season breakdown for that building
- Framing: "For building B1000, Summer roof irradiation is X kWh — dropping to Y kWh in Winter"

---

## Benchmark

**Seasonal ratio (Summer ÷ Winter):**
- Ratio < 2: low seasonal variation — stable year-round performance
- Ratio 2–4: moderate variation — Winter output still meaningful
- Ratio > 4: high seasonal variation — Winter output significantly reduced, storage or grid dependency increases

In the Shanghai case study dataset, the roof Summer/Winter ratio is approximately **4.8** — high variation, meaning Winter production is limited and grid dependency will be significant in cold months.

**Context note:** The LLM reads the city from the weather file and frames seasonal variation in the correct geographic context — Shanghai has hot summers and mild winters, so this ratio is expected. A Nordic location would show a much more extreme ratio.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Plain-language explanation of each season's irradiation value per surface
- The Summer/Winter ratio calculated and explained
- Comparison to typical ranges for the project's climate zone
- Note that hours per season differ (Summer has more daylight hours) — so per-hour intensity differences are smaller than total kWh differences suggest

**Visualization:** Grouped bar chart by season
- X axis: seasons (Spring, Summer, Autumn, Winter)
- Bars: one colour per surface (roof, south wall, east wall, west wall, north wall)
- Source data shown below chart

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Summer generates X times more solar energy than Winter — your system is strongly seasonal"
- One sentence on which surface shows the most consistent performance across seasons (often south wall)
- One sentence on what this means for annual yield reliability

**Visualization:** Line chart across seasons
- One line per surface
- X axis: Spring → Summer → Autumn → Winter
- Clearly shows the peak and drop-off
- Designed to be readable in a presentation

---

### If "Design implication" selected:
**What the LLM produces:**
- Concrete recommendation on whether seasonal variation is a design concern for this project
- If ratio > 4: flag that Winter grid dependency is high — recommend investigating storage or demand-matching (links to Demand vs Supply skill)
- If ratio < 2: confirm that the system performs reliably year-round — low seasonal risk
- Note on which surfaces are most stable across seasons (useful if consistent output is a priority)

**Visualization:** Seasonal contribution chart
- Stacked bar showing each season's share of annual total (%)
- e.g. Summer 42% / Spring 33% / Autumn 17% / Winter 8%
- Makes the imbalance immediately visible

---

## Common Pitfalls

- **Hours per season are not equal:** Summer has more daylight hours than Winter. Total kWh difference is therefore partly due to day length, not just radiation intensity. Always note this when explaining numbers.
- **Seasonal labels are CEA-defined:** CEA uses fixed calendar seasons (Spring = Mar–May, Summer = Jun–Aug, Autumn = Sep–Nov, Winter = Dec–Feb). This may not match the user's intuitive understanding of seasons in their climate.
- **Do not alarm unnecessarily:** High Summer/Winter ratios are normal and expected in most climates. Frame it as useful information for energy strategy, not as a problem.

---

## References

- CEA4 solar irradiation output documentation
- IDP 2025 Team 3: seasonal performance analysis used to evaluate facade orientation strategies
- IDP 2024 Team 2: seasonal demand-supply matching used to justify roof PV prioritisation
- Interview — Interviewee C: "We looked at production depending on orientation, time (daily/seasonal)"
