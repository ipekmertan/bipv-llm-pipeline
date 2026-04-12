---
name: impact-and-viability--carbon-impact--carbon-payback
description: Use when the architect wants to understand how long it takes for a BIPV system to offset its own manufacturing emissions, and what the net carbon benefit is over its lifetime. Combines CEA lifecycle emissions data with operational offset data to calculate carbon payback period.
intent: Give the architect a clear, time-based picture of the BIPV system's full carbon story — from the emissions cost of manufacturing the panels to the point where cumulative avoided emissions outweigh that cost, and the total net carbon benefit over the system's lifetime.
type: component
position_in_tree: "Goal → Impact and Viability → Carbon Impact → Carbon Payback"
---

## Purpose

Answer the question: **"How long does it take for this BIPV system to offset its own manufacturing emissions — and what is the net carbon benefit over its lifetime?"**

This skill combines two pieces of information from CEA:
- **Embodied carbon of PV panels** — the carbon emitted to manufacture, transport and install them
- **Annual carbon offset from operation** — the carbon avoided each year by generating electricity instead of drawing from the grid

From these it calculates the carbon payback period and the total lifetime net carbon benefit.

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.
```

**Lifecycle emissions data** accessed via InputLocator:
```python
locator.get_lifecycle_emissions()
# → lifecycle_emissions_buildings.csv
# PV embodied carbon: production_PV_PV1[kgCO2e]

locator.get_total_emissions_building()
# → Total_emission_building_2100.csv
# Full lifetime emissions including PV production and offsets
```

**Operational emissions data** accessed via InputLocator:
```python
locator.get_operational_emissions()
# → operational_emissions_annually_buildings.csv
# Annual BIPV offset: PV_PV1_GRID_offset[kgCO2e] per year
```

---

## Data Sources

**Primary CEA files accessed via InputLocator:**

| File | What it provides |
|------|-----------------|
| `lifecycle_emissions_buildings.csv` | Embodied carbon of PV panels per panel type (`production_PV_PV{n}[kgCO2e]`) |
| `operational_emissions_annually_buildings.csv` | Annual carbon offset from BIPV (`PV_PV{n}_GRID_offset[kgCO2e]`) |
| `Total_emission_building_2100.csv` | Full lifetime net carbon per building to 2100 |

**Key columns:**
- `production_PV_PV1[kgCO2e]` — embodied carbon of PV1 panels (manufacturing)
- `PV_PV1_GRID_offset[kgCO2e]` — annual carbon avoided by PV1 self-consumption
- `PV_PV1_GRID_export[kgCO2e]` — annual carbon credit from PV1 export

**Carbon Payback Calculation:**
```
embodied_carbon = production_PV_PV{n} (kgCO2e) — from lifecycle file
annual_offset = PV_PV{n}_GRID_offset + PV_PV{n}_GRID_export (kgCO2e/year)
carbon_payback_years = embodied_carbon / annual_offset
lifetime_net_benefit = (annual_offset × panel_lifetime_years) - embodied_carbon
```

**Panel lifetime assumption:** 25–30 years (standard PV panel warranty period). The LLM uses 25 years as default and notes the assumption clearly.

**Panel type comparison:**
If multiple panel types were simulated, the skill calculates payback period for each and compares them — different technologies have different embodied carbon and different generation efficiency.

---

## Scale Behaviour

**District scale:**
- Sums embodied carbon across all installed PV panels district-wide
- Divides by total annual district-wide carbon offset
- Framing: "The district's BIPV system has an embodied carbon of X tCO2e — it pays this back in Y years"

**Cluster scale:**
- Per-building payback periods for named buildings
- Identifies which buildings have the fastest and slowest payback
- Framing: "B1012 (largest roof) pays back in X years — B1011 (smallest installation) takes Y years"

**Building scale:**
- Single building payback calculation
- Panel type comparison if multiple types simulated
- Framing: "Building B1000's PV1 installation pays back its manufacturing carbon in X years — leaving Z years of net carbon benefit within a 25-year lifespan"

---

## Benchmark

**Carbon payback period:**
- < 3 years: excellent — panels are strongly carbon-positive over their lifetime
- 3–8 years: good — standard range for well-sited crystalline silicon panels
- 8–15 years: moderate — still net positive over 25-year lifetime but margin is smaller
- > 15 years: marginal — net carbon benefit over lifetime is limited

**Typical ranges by panel technology (from IDP project data):**
- CdTe (Cadmium-Telluride): shortest payback — lowest embodied carbon
- Monocrystalline silicon: moderate payback — higher embodied carbon but high efficiency
- Organic PV: lowest embodied carbon but lowest efficiency — depends heavily on context

**Context note:** Grid carbon intensity directly affects payback period. A dirty grid (high kgCO2/kWh) means more carbon is avoided per kWh generated — shorter payback. A clean grid means less avoided per kWh — longer payback. The LLM retrieves grid carbon intensity from the project location via internet search.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Embodied carbon of PV panels per type in kgCO2e and tCO2e
- Annual carbon offset from self-consumption and export
- Carbon payback period in years for each panel type
- Remaining net carbon benefit after payback (years × annual offset - embodied)
- Grid carbon intensity context from project location
- Note on assumptions (25-year lifetime, current grid intensity)

**Visualization:** Carbon payback timeline chart
- X axis: years from installation (0 to 25)
- Y axis: cumulative carbon (kgCO2e)
- Line 1: embodied carbon (flat horizontal line — one-time cost at year 0)
- Line 2: cumulative avoided emissions (rising line)
- Crossover point marked: "Carbon neutral in year X"
- One line per panel type if multiple simulated

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your BIPV system pays back its manufacturing carbon in X years — generating Y tCO2e of net benefit over 25 years"
- One sentence on best performing panel type
- One sentence on grid carbon intensity context

**Visualization:** Payback period comparison bar chart
- One bar per panel type showing payback period in years
- 25-year lifetime line marked
- Makes panel type comparison immediately visible

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of whether carbon payback period is acceptable for this project's timeline
- If payback < project lifetime: BIPV is carbon-positive — lead with this in sustainability narrative
- If payback > project lifetime: flag that the carbon argument is weak — other arguments (energy independence, economics) should lead
- Panel type recommendation based on carbon payback
- Note on grid decarbonisation: if the grid is getting cleaner over time, the carbon argument for BIPV weakens — best to install now when the grid is still relatively carbon-intensive
- Links to Operational Carbon Footprint for annual emissions context
- Links to LCOE for economic comparison

**Visualization:** Lifetime net carbon benefit chart
- Stacked bar per panel type: embodied carbon (red) vs lifetime avoided emissions (green)
- Net benefit shown clearly
- Designed for client sustainability presentation

---

## Common Pitfalls

- **Embodied carbon is a one-time cost:** The `production_PV_PV{n}` value in the lifecycle file covers the full lifetime — manufacturing, transport, installation, and end-of-life. It is not an annual value.
- **Grid carbon intensity changes payback dramatically:** A project in a coal-heavy grid vs a renewable-heavy grid can have payback periods differing by 10+ years for the same panels. Always present the grid intensity assumption clearly.
- **Export credit varies by policy:** The `PV_PV{n}_GRID_export` offset depends on whether a feed-in tariff exists — in markets without export compensation, exported electricity has no carbon credit. Flag this if the infrastructure readiness skill indicates no export policy.
- **Panel type naming:** PV1–PV4 are CEA internal identifiers. Cross-reference CEA database to translate to actual technology names for the output.

---

## References

- CEA4 lifecycle emissions output documentation
- IDP 2024 Team 8: carbon payback analysis by panel type — CdTe found to offset embodied emissions within one year
- IDP 2024 Team 2: lifetime LCA analysis comparing embodied vs operational emissions across scenarios
- Interview — Interviewee B: calculated abated emissions manually — noted this was missing from CEA outputs
- Interview — Interviewee C: questioned whether BIPV was worth it in Shanghai context — carbon payback provides the evidence-based answer
