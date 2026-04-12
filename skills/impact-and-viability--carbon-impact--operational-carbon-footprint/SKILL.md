---
name: impact-and-viability--carbon-impact--operational-carbon-footprint
description: Use when the architect wants to understand the operational carbon emissions of their building and how much BIPV reduces them. Reads CEA emissions outputs to show total emissions by source, the carbon offset from BIPV generation, and abated emissions compared to the grid.
intent: Give the architect a clear picture of their building's operational carbon footprint — what it is, what drives it, and how much BIPV reduces it — in terms that connect directly to sustainability goals and client communication.
type: component
position_in_tree: "Goal → Impact and Viability → Carbon Impact → Operational Carbon Footprint"
---

## Purpose

Answer the question: **"How do operational carbon emissions look for this building with BIPV?"**

This skill reads CEA's emissions outputs to present:
- **Total operational emissions** — what the building emits from heating, cooling, hot water, and electricity
- **BIPV carbon offset** — how much the BIPV system reduces emissions by replacing grid electricity
- **Abated emissions vs grid** — how much CO2 the BIPV system avoids compared to drawing everything from the grid
- **Emissions by source** — which energy sources drive the footprint

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.

**Emissions data** accessed via InputLocator:
```python
locator.get_operational_emissions()
# → operational_emissions_annually_buildings.csv
# Key columns: E_sys[kgCO2e], Qhs_sys[kgCO2e], Qcs_sys[kgCO2e]
# PV offset: PV_PV1_GRID_offset[kgCO2e], PV_PV1_GRID_export[kgCO2e]

locator.get_total_yearly_operational()
# → Total_yearly_operational_building.csv
# Annual totals per building including PV offsets
```

---

## Data Sources

**Primary CEA files accessed via InputLocator:**

| File | What it provides |
|------|-----------------|
| `operational_emissions_annually_buildings.csv` | Annual emissions per building per energy source |
| `Total_yearly_operational_building.csv` | Annual total emissions per building including PV offsets |

**Key columns used:**
- `E_sys[kgCO2e]` — electricity-related emissions
- `Qhs_sys[kgCO2e]` — heating emissions
- `Qww_sys[kgCO2e]` — hot water emissions
- `Qcs_sys[kgCO2e]` — cooling emissions
- `GRID[kgCO2e]` — total grid-sourced emissions
- `PV_PV1_GRID_offset[kgCO2e]` — carbon avoided by BIPV self-consumption (negative value)
- `PV_PV1_GRID_export[kgCO2e]` — carbon credit from exported electricity (negative value)

**Derived metrics:**
```
total_operational = E_sys + Qhs_sys + Qww_sys + Qcs_sys (kgCO2e)
bipv_offset = sum of PV_PV{n}_GRID_offset (kgCO2e) — negative, reduces footprint
net_emissions = total_operational + bipv_offset
abatement_rate = bipv_offset / total_operational × 100%
emissions_per_m2 = net_emissions / GFA_m2 (kgCO2e/m²)
```

---

## Scale Behaviour

**District scale:**
- Sums all building emissions and all BIPV offsets
- Framing: "The district emits X tCO2e/year — BIPV reduces this by Y% to Z tCO2e/year"

**Cluster scale:**
- Shows emissions and offset per building within cluster
- Identifies highest and lowest emitting buildings
- Framing: "B1012 has the highest absolute emissions but also the largest BIPV offset"

**Building scale:**
- Single building emissions breakdown by end-use
- Framing: "Building B1000 emits X kgCO2e/year — cooling accounts for Y%, offset by Z kgCO2e from BIPV"

---

## Benchmark

**Operational emissions intensity:**
- < 20 kgCO2e/m²/year: low — high performance building
- 20–50 kgCO2e/m²/year: moderate — typical urban building
- 50–100 kgCO2e/m²/year: high — significant improvement opportunity
- > 100 kgCO2e/m²/year: very high — major intervention needed

**BIPV abatement rate:**
- > 30%: strong carbon argument for BIPV
- 15–30%: moderate — meaningful but not transformative
- < 15%: limited carbon impact — economic or architectural argument may be stronger

**Grid carbon intensity context:**
The LLM reads the project location from the weather file and retrieves the local grid carbon intensity via internet search — this is the key factor determining how much carbon the BIPV system actually avoids. A clean grid (low kgCO2/kWh) means BIPV avoids less carbon per kWh generated.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Total annual emissions before and after BIPV offset
- Breakdown by end-use: heating / cooling / hot water / electricity
- Breakdown by energy source: which fuels drive the footprint
- BIPV offset per panel type if multiple simulated
- Emissions per m² of floor area vs benchmark
- Grid carbon intensity context from project location

**Visualization:** Stacked bar chart — emissions breakdown
- One bar: total emissions by end-use (heating/cooling/hot water/electricity)
- Second bar: net emissions after BIPV offset shown as reduction
- Clear visual of how much BIPV cuts the footprint

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your building emits X tCO2e/year — BIPV reduces this by Y% to Z tCO2e"
- One sentence on dominant emission source
- One sentence on BIPV's carbon contribution in context

**Visualization:** Before/after emissions comparison
- Two simple bars: with and without BIPV
- Reduction highlighted clearly
- Designed for client presentation

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of whether BIPV makes a meaningful carbon argument for this project
- If grid is carbon-intensive: strong carbon case — lead with emissions reduction
- If grid is already clean: weaker carbon case — energy independence or economic argument may be stronger
- Recommendation on which end-use to target for greatest carbon reduction (usually cooling in hot climates)
- Links to Carbon Payback skill for full lifecycle picture
- Links to Basic Economic Signal for grid carbon intensity context

**Visualization:** Carbon reduction waterfall chart
- Shows: baseline emissions → BIPV self-consumption offset → BIPV export credit → net emissions
- Makes the contribution of each BIPV benefit visible

---

## Common Pitfalls

- **PV offset values are negative:** CEA correctly reports BIPV offsets as negative kgCO2e — they reduce the footprint. Always present these as reductions, not additions.
- **Grid carbon intensity changes over time:** In long-term scenarios (e.g. 2060), the grid may be much cleaner — reducing the carbon argument for BIPV. The LLM flags this for future-scenario projects.
- **Operational emissions only:** This skill covers operational emissions only — not embodied carbon of the building structure or PV panels. That is covered by the Carbon Payback skill.
- **Cooling dominance in hot climates:** In Shanghai and similar climates, cooling emissions typically dominate the operational footprint. The LLM frames this in context.

---

## References

- CEA4 operational emissions output documentation
- IDP 2025 Team 3: operational emissions analysis comparing base case vs new design
- IDP 2024 Team 2: BIPV decarbonisation potential analysis showing PV has highest impact
- IDP 2024 Team 8: grid carbon intensity used as key input for emissions calculations
- Interview — Interviewee B: calculated abated emissions manually as a derived metric
