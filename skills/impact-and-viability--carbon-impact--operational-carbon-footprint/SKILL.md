---
name: "impact-and-viability--carbon-impact--carbon-footprint"
description: "Use when the architect wants to understand the building's electricity-related carbon footprint and how much BIPV reduces it. Uses CEA demand/PV results and grid-carbon data when available."
intent: "Give the architect a clear picture of the building's carbon footprint from electricity use, the avoided carbon from BIPV generation, and whether BIPV is a strong carbon argument for the project."
type: "component"
position_in_tree: "Goal → Impact and Viability → Carbon Impact → Carbon Footprint"
---

## Purpose

Answer the question: **"How much carbon footprint does electricity use create here, and how much does BIPV avoid?"**

This skill should be concise and non-redundant. It presents:
- **Baseline electricity carbon footprint** — carbon if the same electricity demand came from the grid
- **BIPV avoided carbon** — how much carbon the simulated PV generation avoids
- **Net electricity carbon footprint** — remaining grid-related electricity carbon after BIPV
- **Carbon argument strength** — whether BIPV is a strong, moderate, or weak carbon story for the concept

Do not repeat Carbon Payback content. This skill is about the annual footprint reduction; Carbon Payback is about how long panels take to offset their own manufacturing carbon.

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

**Primary files used by the app:**

| File | What it provides |
|------|-----------------|
| `PV_PV{n}_total.csv` and `PV_PV{n}_total_buildings.csv` | PV generation at district/building scale |
| `B{id}.csv` and demand outputs | electricity demand at building/cluster/district scale |
| `GRID.csv` | grid carbon factor when available |

**Key columns used:**
- `E_PV_gen_kWh` — PV electricity generation
- `E_sys_kWh` — electricity demand
- `GHG_kgCO2MJ` or similar grid-carbon factor where available

**Derived metrics:**
```
baseline_electricity_carbon = annual_electricity_demand × grid_carbon
avoided_carbon = min(PV_generation, electricity_demand) × grid_carbon
net_electricity_carbon = baseline_electricity_carbon - avoided_carbon
abatement_rate = avoided_carbon / baseline_electricity_carbon × 100%
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
- Baseline electricity carbon footprint
- BIPV avoided carbon
- Net electricity carbon footprint after BIPV
- Abatement rate in %
- Grid carbon factor used and whether it came from project data or fallback context
- Keep this as a compact table plus one short interpretation paragraph.

**Visualization:** Before/after carbon footprint chart
- Baseline grid-electricity carbon
- BIPV avoided carbon shown as a reduction
- Net electricity carbon after BIPV

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "BIPV reduces electricity-related carbon by X tCO2e/year, about Y% of the building's electricity footprint."
- One sentence on whether this is a strong, moderate, or weak carbon argument.
- One design/client implication.

**Visualization:** Before/after emissions comparison
- Two simple bars: with and without BIPV
- Reduction highlighted clearly
- Designed for client presentation

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of whether BIPV makes a meaningful annual carbon argument for this project.
- If avoided carbon is high: lead with emissions reduction in the client narrative.
- If avoided carbon is low because the grid is clean or PV generation is small: lead with energy independence, regulation, economics, or architectural integration instead.
- Keep this mode focused on design and client framing, not payback years.

**Visualization:** Carbon reduction waterfall chart
- Shows: baseline emissions → BIPV self-consumption offset → BIPV export credit → net emissions
- Makes the contribution of each BIPV benefit visible

---

## Common Pitfalls

- **PV offset values are negative:** CEA correctly reports BIPV offsets as negative kgCO2e — they reduce the footprint. Always present these as reductions, not additions.
- **Grid carbon intensity changes over time:** In long-term scenarios (e.g. 2060), the grid may be much cleaner — reducing the carbon argument for BIPV. The LLM flags this for future-scenario projects.
- **Electricity carbon only unless emissions files are supplied:** Do not imply full building operational carbon if only PV/demand/grid-carbon data are available.
- **Carbon Payback is separate:** Do not discuss how many years panels take to offset manufacturing carbon here.
- **Cooling dominance in hot climates:** In Shanghai and similar climates, cooling emissions typically dominate the operational footprint. The LLM frames this in context.

---

## References

- CEA4 operational emissions output documentation
- IDP 2025 Team 3: operational emissions analysis comparing base case vs new design
- IDP 2024 Team 2: BIPV decarbonisation potential analysis showing PV has highest impact
- IDP 2024 Team 8: grid carbon intensity used as key input for emissions calculations
- Interview — Interviewee B: calculated abated emissions manually as a derived metric
