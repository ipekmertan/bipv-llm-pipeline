---
name: performance-estimation--energy-generation
description: Use when the architect wants to understand how much electricity their BIPV system produces — across the year, by season, by time of day, and broken down by surface and panel type. Reads CEA PV yield outputs and presents generation in design-relevant terms.
intent: Give the architect a complete picture of their BIPV system's electricity production — from annual totals to seasonal variation to daily profiles — so they can understand system scale, compare panel types, and communicate energy performance to clients and engineers.
type: component
position_in_tree: "Goal → Performance Estimation → Energy Generation"
---

## Purpose

Answer the question: **"How much electricity does my BIPV system produce across the year?"**

This skill reads CEA's hourly PV simulation outputs and presents electricity generation at multiple timescales — annual totals, seasonal breakdowns, and typical daily profiles — in a way that is immediately meaningful for architectural decision-making.

It covers:
- **Annual total generation** — how much in total, which surfaces contribute most
- **Seasonal variation** — how output changes across Spring, Summer, Autumn, Winter
- **Daily profile** — when during the day the system generates and peaks
- **Panel type comparison** — if multiple panel types were simulated

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.

## Data Sources

**Primary CEA files accessed via InputLocator:**

| Scale | File |
|-------|------|
| District | `PV_PV{n}_total.csv` (8760 hourly rows) |
| Cluster | `PV_PV{n}_total_buildings.csv` (filtered to named buildings) |
| Building | `PV_PV{n}_total_buildings.csv` (single building row) + hourly from total |

**Key columns used:**
- `E_PV_gen_kWh` — total electricity generated per hour
- `PV_roofs_top_E_kWh` — roof contribution per hour
- `PV_walls_south_E_kWh` — south facade contribution per hour
- `PV_walls_east_E_kWh` — east facade contribution
- `PV_walls_west_E_kWh` — west facade contribution
- `PV_walls_north_E_kWh` — north facade contribution
- `PV_roofs_top_m2`, `PV_walls_*_m2` — installed area per surface
- `area_PV_m2` — total installed PV area
- `date` — timestamp for seasonal and daily aggregation

**Derived metrics:**
- Annual total generation (kWh/year)
- Generation per m² of installed area (kWh/m²/year)
- Surface contribution breakdown (% per surface)
- Seasonal totals: Spring / Summer / Autumn / Winter
- Summer/Winter ratio (variability indicator)
- Typical daily profile: average generation per hour of day
- Peak generation hour
- Panel type comparison if multiple types simulated

---

## Scale Behaviour

**District scale:**
- Annual total across all buildings
- Seasonal and daily profiles aggregated across district
- Framing: "The district BIPV system generates X MWh/year — Summer accounts for Y% of annual output"

**Cluster scale:**
- Per-building annual totals for named buildings
- Cluster-level seasonal and daily profiles
- Framing: "Across this cluster, B1012 generates the most at X MWh/year — B1011 the least at Y MWh"

**Building scale:**
- Single building annual total with surface breakdown
- That building's seasonal variation and typical daily profile
- Framing: "Building B1000 generates X kWh/year entirely from roof PV — peaking at noon and generating negligible output after 5pm"

---

## Benchmark

**Generation intensity:**
- > 150 kWh/m²/year: excellent
- 100–150 kWh/m²/year: good — typical well-sited BIPV
- 50–100 kWh/m²/year: moderate — partially shaded or lower-efficiency panels
- < 50 kWh/m²/year: low — consider whether installation is worthwhile

**Seasonal variation (Summer ÷ Winter ratio):**
- < 2: low variation — stable year-round
- 2–4: moderate — manageable seasonal swing
- > 4: high — Winter output significantly reduced

**Scale reference for client communication:**
- 1 MWh ≈ annual electricity use of one European apartment
- The LLM uses project location to contextualise against local benchmarks

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Annual total generation in kWh and MWh with plain-language scale reference
- Surface breakdown: roof vs each facade orientation — % contribution each
- Generation per m² of installed area vs benchmark
- Seasonal totals and Summer/Winter ratio with explanation of what drives variation
- Typical daily profile: peak generation hour, hours of meaningful output
- Panel type comparison if multiple types simulated

**Visualization:** Three-part output:
1. Stacked bar chart — annual generation by surface
2. Seasonal bar chart — Spring / Summer / Autumn / Winter totals
3. Typical daily profile line chart — average generation per hour for Summer and Winter day

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your BIPV system generates X MWh/year — equivalent to powering Y apartments"
- One sentence on dominant surface and its share
- One sentence on seasonal reliability: "Summer generates X times more than Winter"
- One sentence on daily peak hour

**Visualization:** Donut chart showing surface contribution + seasonal summary card below

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of generation scale relative to building size and context
- Whether seasonal variation is a design concern for this building type and location
- Whether the daily profile aligns with likely building use patterns
- Whether expanding installed area would meaningfully increase output
- Links to Self Sufficiency skill to understand how this generation compares to demand

**Visualization:** Generation improvement scenario
- Current generation vs potential with south facade added / east+west facades added
- Shows architect where additional area would have most impact

---

## Common Pitfalls

- **Panel area vs roof area:** `area_PV_m2` is installed panel area after threshold filtering — not total roof area. Always clarify.
- **North wall zeros are correct:** North walls are filtered out by CEA's radiation threshold. Expected behaviour, not a data error.
- **Panel type naming:** PV1–PV4 are CEA internal identifiers. Cross-reference CEA database to translate to actual technology names for architect-facing output.
- **Seasonal hours differ:** Summer has more daylight hours than Winter — total kWh difference is partly due to day length. Always note this.
- **Southern hemisphere seasons:** Read latitude from weather file to apply correct seasonal labels.

---

## References

- CEA4 PV simulation output documentation
- IDP 2025 Team 3: annual PV generation analysis by surface, orientation, and season
- IDP 2024 Team 8: PV electricity generation aggregated by building type with seasonal breakdown
- Interview — Interviewee B: "Annual PV generation (roof/facade/building)" as primary output; also wanted daily/seasonal profiles
- Interview — Interviewee D: "Building-specific total energy production, energy per surface area, hourly production"

---

## Radiation Threshold — Parameter Check Context

The `annual-radiation-threshold` in CEA determines which surfaces are included in the PV simulation. The app's parameter check computes a project-specific carbon threshold using Happle et al. (2019) and McCarty et al. (2025):

`I_threshold = EmBIPV / (Gridem × η × PR × lifetime)`

The calculation uses local grid carbon intensity, selected PV type embodied carbon, PV type efficiency, PR = 0.75 and lifetime = 25 years unless a project-specific value is supplied. The stricter 10-year carbon payback threshold is shown as context where useful.

When multiple panel types are run together, CEA applies one threshold to all. The parameter check first identifies the best overall simulated PV option from actual generation, lifetime carbon intensity, and installed cost, then applies the carbon threshold to that option. If that option's carbon threshold is above the facade-screening limit, the app shows an LCOE fallback threshold so early-design facade potential is not erased.

**Sources:** Happle et al. (2019). J. Phys.: Conf. Ser. 1343, 012077. · McCarty et al. (2025). J. Phys.: Conf. Ser. 3140, 032006. · CEA Learning Camp PV panel threshold workflow.
