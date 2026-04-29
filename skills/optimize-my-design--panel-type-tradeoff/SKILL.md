---
name: "optimize-my-design--panel-type-tradeoff"
description: "Use when the architect wants to compare BIPV panel types across efficiency, cost, embodied carbon, and actual yield for their specific project. Reads CEA PV yield outputs for all simulated panel types and the CEA panel database to produce a multi-criteria comparison."
intent: "Help the architect choose the right panel technology for their specific project context by comparing all simulated panel types across the metrics that matter for design decisions — not just efficiency, but cost, carbon, yield, and architectural suitability."
type: "component"
position_in_tree: "Goal → Performance Estimation → Panel Type Trade-off"
---

## Purpose

Answer the question: **"How do different panel types compare across efficiency, cost, and carbon for my project?"**

This skill compares the BIPV panel types simulated in the CEA project (PV1–PV4) across multiple dimensions — actual electricity yield, installation cost, embodied carbon, and lifecycle performance — giving the architect a clear, evidence-based basis for choosing the right technology.

Unlike a generic panel comparison, this skill uses the **actual simulation results** for the architect's specific project — so the comparison reflects real shading, orientation, and surface area conditions, not theoretical maximums.

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.

## Data Sources

**From CEA PV yield files (per panel type):**
- `E_PV_gen_kWh` — annual generation per panel type
- `area_PV_m2` — installed area per panel type

**From CEA panel database (`PHOTOVOLTAIC_PANELS.csv`):**

| Column | Meaning |
|--------|---------|
| `code` | Panel identifier (PV1, PV2, PV3, PV4) |
| `description` | Technology name |
| `PV_n` | Panel efficiency (fraction, e.g. 0.184 = 18.4%) |
| `module_embodied_kgco2m2` | Embodied carbon (kgCO2/m²) |
| `cost_facade_euro_m2` | Facade installation cost (€/m²) |
| `cost_roof_euro_m2` | Roof installation cost (€/m²) |
| `LT_yr` | Panel lifetime (years) |
| `primary_energy_kWh_m2` | Primary energy for manufacturing (kWh/m²) |

**CEA Panel Database (from this project's database):**

| Panel | Technology | Efficiency | Embodied Carbon | Facade Cost | Roof Cost |
|-------|-----------|-----------|----------------|-------------|-----------|
| PV1 | Crystalline Silicon (cSi) | 18.5% | 255.8 kgCO2/m² | €345.72/m² | €254.72/m² |
| PV2 | Monocrystalline Silicon (mcSi) | 17.5% | 191.2 kgCO2/m² | €329.58/m² | €238.58/m² |
| PV3 | Cadmium-Telluride (CdTe) | 17.6% | 47.6 kgCO2/m² | €330.54/m² | €239.54/m² |
| PV4 | CIGS | 9.9% | 75.9 kgCO2/m² | €356.06/m² | €265.06/m² |

**Note:** These values are read from the CEA database at runtime — the plugin always uses the actual database values, not these hardcoded figures. They are shown here for reference only.

---

## Derived Metrics (calculated per panel type)

```
yield_per_m2 = E_PV_gen_kWh / area_PV_m2  (kWh/m²/year)
total_cost = area_PV_m2 × cost_per_m2  (roof or facade depending on surface)
total_embodied_carbon = area_PV_m2 × module_embodied_kgco2m2  (kgCO2)
annual_carbon_offset = PV_PV{n}_GRID_offset  (kgCO2/year)
carbon_payback_years = total_embodied_carbon / annual_carbon_offset
LCOE = (total_cost + lifetime_O&M) / (E_PV_gen_kWh × LT_yr)  (€/kWh)
```

---

## Scale Behaviour

**District scale:**
- Compares panel types across total district generation, cost, and carbon
- Identifies which panel type gives best district-level performance
- Framing: "At district scale, PV3 (CdTe) generates X MWh vs PV1 (cSi) at Y MWh — at Z% lower embodied carbon"

**Cluster scale:**
- Same comparison for the named cluster of buildings
- Useful when cluster has a specific use type that favours one technology

**Building scale:**
- Panel type comparison for a single building
- Most relevant when architect has design freedom over panel choice for that building
- Framing: "For building B1000, PV3 offers the best carbon payback at X years vs PV1 at Y years"

---

## Benchmark

**Efficiency:**
- PV1 (cSi): 18.5% — highest efficiency in this database
- PV2 (mcSi): 17.5% — slightly lower
- PV3 (CdTe): 17.6% — similar to mcSi but much lower embodied carbon
- PV4 (CIGS): 9.9% — significantly lower efficiency

**Embodied carbon (kgCO2/m²):**
- PV3 (CdTe): 47.6 — lowest by far
- PV4 (CIGS): 75.9 — second lowest
- PV2 (mcSi): 191.2 — moderate
- PV1 (cSi): 255.8 — highest

**Key insight from IDP project data:**
CdTe (PV3) consistently offers the best balance of efficiency, cost, and embodied carbon — it offsets its manufacturing emissions within approximately one year of operation. The LLM frames this finding clearly but always shows the full comparison so the architect can make their own decision.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Table comparing all four panel types across: efficiency, actual yield, cost, embodied carbon, LCOE, carbon payback period
- Plain-language explanation of what each metric means
- Which panel type leads on each individual metric
- Note that actual yield reflects real simulation conditions — not theoretical maximum

**Visualization:** Multi-criteria comparison radar chart
- One axis per metric: efficiency / yield / cost / embodied carbon / carbon payback
- One line per panel type
- Makes trade-offs immediately visible

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline identifying the overall best-performing panel type for this project
- One sentence on what drives that recommendation (usually CdTe for carbon, cSi for yield)
- One sentence on the biggest trade-off the architect needs to be aware of

**Visualization:** Panel comparison scorecard
- Simple table: panel type × metric
- Traffic light colouring: green = best / amber = middle / red = weakest per metric
- Designed for quick decision-making

---

### If "Design implication" selected:
**What the LLM produces:**
- Recommendation on which panel type to use and why — framed by project priorities:
  - If carbon is priority: recommend PV3 (CdTe) — lowest embodied carbon, fast payback
  - If yield is priority: recommend PV1 (cSi) — highest efficiency
  - If cost is priority: recommend PV2 (mcSi) — good balance
  - If CIGS (PV4): flag significantly lower efficiency — only recommend if specific aesthetic reasons
- Note on architectural suitability: different panel types have different visual appearances — the architect may have aesthetic constraints
- Links to Carbon Payback skill for full lifetime carbon comparison
- Links to Cost Analysis skill for detailed financial comparison

**Visualization:** Decision matrix
- Rows: panel types
- Columns: carbon priority / yield priority / cost priority
- Best choice highlighted per priority
- Designed for design team or client discussion

---

## Common Pitfalls

- **Efficiency ≠ yield:** Higher efficiency means more electricity per m² of panel — but if less area meets the threshold, total yield may not be highest. Always use actual simulation yield, not just efficiency.
- **Cost is surface-dependent:** Facade installation costs are significantly higher than roof costs for all panel types. Always use the correct cost column based on where panels are installed.
- **PV4 (CIGS) low efficiency:** At 9.9%, CIGS generates significantly less than other types per m². This is often overlooked when comparing headline numbers — always flag it clearly.
- **Panel type naming:** Always translate PV1/PV2/PV3/PV4 to technology names in the output. Architects do not know what PV3 means — they need to see "CdTe (Cadmium-Telluride)".
- **Database values may be customised:** The plugin always reads from the actual project database — if the architect or their institution has customised the panel database, those values are used. Never hardcode the values above.

---

## References

- CEA4 panel database: `database/COMPONENTS/CONVERSION/PHOTOVOLTAIC_PANELS.csv`
- IDP 2024 Team 8: parametric study across PV types and thresholds — CdTe found optimal for cost/carbon balance
- IDP 2024 Team 2: panel type comparison showing CdTe offsets embodied emissions within one year
- Interview — Interviewee B: selected CdTe based on irradiation, demand, and self-consumption analysis
- Interview — Interviewee C: explicitly questioned whether panel type choice made a meaningful difference — this skill answers that directly

---

## Radiation Threshold & Panel Type

CEA applies a single `annual-radiation-threshold` parameter to **all panel types simultaneously** during a simulation run. This matters because each panel type has a different embodied carbon, which means the carbon-break-even irradiation threshold differs per type:

| Panel | Embodied Carbon | Threshold (Switzerland, 0.042 kgCO₂/kWh) | Threshold (Singapore, 0.408 kgCO₂/kWh) |
|-------|----------------|------------------------------------------|------------------------------------------|
| PV1 (cSi) | 255.8 kgCO₂/m² | 1200 kWh/m²/year (capped) | 800 kWh/m²/year (capped) |
| PV2 (mcSi) | 191.2 kgCO₂/m² | 1200 kWh/m²/year (capped) | 800 kWh/m²/year (capped) |
| PV3 (CdTe) | 47.6 kgCO₂/m² | 800 kWh/m²/year | 800 kWh/m²/year |
| PV4 (CIGS) | 75.9 kgCO₂/m² | ~970 kWh/m²/year | 800 kWh/m²/year |

**Formula (Happle et al. 2019):**
`I_threshold = EmBIPV / (em_grid × η × PR × LT)`

Where PR = 0.75 and LT = 25yr (Galimshina et al. 2024).

**When multiple panel types are run together:** CEA uses one threshold for all. The app recommends setting the threshold to the **highest value among the simulated panel types**. Alternatively, run each panel type in a separate CEA simulation with its own threshold.

**Sources:**
- Happle et al. (2019). J. Phys.: Conf. Ser. 1343, 012077.
- Galimshina et al. (2024). Renewable Energy 236, 121404.
- McCarty et al. (2025). Renew. Sustain. Energy Rev. 211, 115326.
