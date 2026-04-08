---
name: performance-estimation--energy-generation
description: Use when the architect wants to understand how much electricity the BIPV system generates across the year, broken down by surface and panel type. Reads CEA PV yield outputs and presents total generation in design-relevant terms.
intent: Translate CEA's hourly PV yield data into annual, seasonal and surface-level generation figures that architects can use to understand system scale, compare panel types, and communicate energy performance to clients.
type: component
position_in_tree: "Goal → Performance Estimation → Energy Generation"
---

## Purpose

Answer the question: **"How much electricity does this BIPV system generate across the year?"**

This skill reads CEA's PV simulation outputs and presents total electricity generation in a way that is meaningful for architectural decision-making — broken down by surface, by panel type, and in terms that connect to the building's energy context.

---

## CEA4 Integration

This skill runs as a CEA4 plugin. All data is read automatically via the CEA4 `InputLocator`.

**Location context** read automatically from the project weather file:
```python
locator.get_weather()  # → city, latitude, longitude
```

**PV yield data** accessed via InputLocator:
```python
locator.get_pv_results(panel_type="PV1")
# → PV_PV1_total.csv (8760 hourly rows, district level)
# → PV_PV1_total_buildings.csv (annual totals per building)
# Repeated for PV2, PV3, PV4 if simulated
```

---

## Data Sources

**Primary CEA files accessed via InputLocator:**

| Scale | File |
|-------|------|
| District | `PV_PV{n}_total.csv` (8760 rows) |
| Cluster | `PV_PV{n}_total_buildings.csv` (filtered to named buildings) |
| Building | `PV_PV{n}_total_buildings.csv` (single building row) |

**Key columns used:**
- `E_PV_gen_kWh` — total electricity generated (kWh)
- `PV_roofs_top_E_kWh` — roof contribution (kWh)
- `PV_walls_south_E_kWh` — south facade contribution (kWh)
- `PV_walls_east_E_kWh` — east facade contribution (kWh)
- `PV_walls_west_E_kWh` — west facade contribution (kWh)
- `PV_walls_north_E_kWh` — north facade contribution (kWh)
- `PV_roofs_top_m2` — installed roof area (m²)
- `PV_walls_*_m2` — installed facade area per orientation (m²)
- `area_PV_m2` — total installed PV area (m²)
- `date` — timestamp (hourly file only)

**Derived metrics calculated by skill:**
- Annual total generation (kWh/year)
- Generation per m² of installed area (kWh/m²/year)
- Surface contribution breakdown (% per surface)
- Panel type comparison (if multiple PV types simulated)

---

## Scale Behaviour

**District scale:**
- Uses `PV_PV{n}_total.csv` aggregated to annual totals
- Framing: "The district BIPV system generates X MWh/year across Y m² of installed panels"

**Cluster scale:**
- Uses `PV_PV{n}_total_buildings.csv` filtered to named buildings
- Ranks buildings by generation contribution
- Framing: "Across buildings [B1, B2, B3], total generation is X MWh/year — B1012 contributes the most at Y MWh"

**Building scale:**
- Single building row from `PV_PV{n}_total_buildings.csv`
- Shows surface breakdown for that building
- Framing: "Building B1000 generates X kWh/year — entirely from roof PV (Y m²)"

---

## Benchmark

**Generation intensity benchmarks:**
- > 150 kWh/m²/year: high — excellent panel performance
- 100–150 kWh/m²/year: good — typical well-sited BIPV
- 50–100 kWh/m²/year: moderate — partially shaded or low-efficiency panels
- < 50 kWh/m²/year: low — consider whether installation is worthwhile

**Scale reference points (for architect communication):**
- 1 MWh = approximately the annual electricity use of one European apartment
- The LLM uses the project location to contextualise against local energy consumption benchmarks

**Panel type comparison:**
If multiple panel types were simulated, the skill compares total generation and generation per m² across types, directly from the CEA output files.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Total annual generation in kWh and MWh
- Generation per m² of installed area
- Surface breakdown: how much comes from roof vs each facade orientation
- Panel type comparison if multiple types simulated
- Plain-language scale reference: "This is equivalent to powering X apartments for a year"

**Visualization:** Stacked bar chart by surface
- One bar per building (cluster/district) or one bar total (building scale)
- Stacked by surface: roof / south wall / east wall / west wall / north wall
- Y axis: annual generation (kWh)
- Source data shown below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your BIPV system generates X MWh/year — roof accounts for Y% of total"
- One sentence on the most and least productive surfaces
- One sentence on generation intensity compared to benchmark

**Visualization:** Donut chart
- Segments: roof / south wall / east wall / west wall / north wall
- Total generation shown in centre
- Simple and presentation-ready

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of whether the generation scale is appropriate for the building's energy needs
- If roof dominates: confirmation that roof-first strategy is working
- If facade contribution is significant: flag which orientations are performing and whether they justify the added complexity
- Recommendation on whether to expand or reduce installed area
- Links to Self Sufficiency skill for demand context

**Visualization:** Generation vs installed area scatter plot
- One point per building (cluster/district scale)
- X axis: installed area (m²)
- Y axis: annual generation (kWh)
- Identifies over and underperforming buildings relative to their installed area

---

## Common Pitfalls

- **Panel area vs roof area:** `area_PV_m2` is the installed panel area — not the total roof area. CEA applies the radiation threshold and coverage ratio before calculating this. Always clarify this distinction when presenting numbers.
- **North wall zeros:** North wall values are typically 0 because CEA's threshold filter excludes them. Do not present this as a data error — it is correct behaviour.
- **Panel type naming:** PV1, PV2, PV3, PV4 are CEA's internal panel type identifiers. The skill should cross-reference the CEA database to translate these into actual panel technology names (e.g. monocrystalline, CdTe) for architect-facing output.

---

## References

- CEA4 PV simulation output documentation
- IDP 2025 Team 3: annual PV generation analysis by surface and orientation
- IDP 2024 Team 8: PV electricity generation aggregated by building type
- Interview — Interviewee B: "Annual PV generation (roof/facade/building)" as key output sought
- Interview — Interviewee D: "Building-specific total energy production" as desired metric
