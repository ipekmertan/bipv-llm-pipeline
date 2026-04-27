---
name: performance-estimation--self-sufficiency
description: Use when the architect wants to understand how their BIPV generation compares to what the building actually needs — covering self-sufficiency ratio, demand vs supply time match, seasonal grid dependency, and what would improve coverage.
intent: Give the architect a complete picture of the relationship between their BIPV system's output and their building's energy demand — from the annual ratio to the hourly alignment — so they understand how energy-independent the building is and what would meaningfully improve it.
type: component
position_in_tree: "Goal → Performance Estimation → Self Sufficiency"
---

## Purpose

Answer the question: **"How does my BIPV generation compare to what my building actually needs?"**

Self-sufficiency is the key metric that connects supply to demand — it tells the architect what fraction of the building's annual electricity needs are met by on-site solar generation. This skill goes beyond the single ratio to also show *when* generation and demand align, *when* the building is grid-dependent, and what would improve the situation.

It covers:
- **Self-sufficiency ratio** — annual generation as % of annual electricity demand
- **Demand vs supply time match** — when during the day and year generation meets demand
- **Seasonal grid dependency** — which seasons the building relies most on the grid
- **Improvement scenarios** — what would meaningfully increase self-sufficiency

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.
## Data Sources

| `PV_PV{n}_total_buildings.csv` | Annual PV generation per building (kWh) |
| `demand/Total_demand.csv` | Annual electricity demand per building (MWhyr) |
| `demand/B{id}.csv` | Hourly electricity demand per building (kWh) |

**Key columns:**
- `E_PV_gen_kWh` — hourly PV generation
- `E_sys_kWh` — hourly electricity demand
- `E_sys_MWhyr` — annual electricity demand per building
- `GFA_m2` — gross floor area (for normalisation)
- `date` — timestamp (for hourly alignment)

**Derived metrics:**
```
self_sufficiency = E_PV_gen_annual / E_sys_annual × 100%
self_consumed = min(E_PV_gen, E_sys) per hour → summed annually
surplus = max(E_PV_gen - E_sys, 0) per hour → exported to grid
deficit = max(E_sys - E_PV_gen, 0) per hour → imported from grid
self_consumption_ratio = self_consumed / E_PV_gen_annual × 100%
```

---

## Scale Behaviour

**District scale:**
- Sums all building PV generation and all building demand
- Also shows per-building self-sufficiency to identify strongest and weakest performers
- Framing: "The district BIPV system covers X% of total electricity demand — ranging from Y% (B1012) to Z% (B1011) per building"

**Cluster scale:**
- Cluster aggregate ratio plus per-building breakdown
- Framing: "Across this cluster, self-sufficiency averages X% — peak mismatch occurs between 4pm–8pm when solar generation drops but cooling demand remains high"

**Building scale:**
- Single building ratio with hourly time-match analysis
- Most revealing scale — shows the specific building's demand pattern against its generation
- Framing: "Building B1000 covers X% of its annual electricity demand from BIPV — but Y% of generation occurs when demand is low, reducing effective coverage"

---

## Benchmark

**Self-sufficiency ratio:**
- > 50%: high — building is significantly energy-independent
- 30–50%: good — meaningful contribution, still grid-dependent for majority
- 15–30%: moderate — useful but limited impact on grid dependency
- < 15%: low — BIPV covers only a small fraction of demand

**Self-consumption ratio:**
- > 70%: excellent time match — most generation directly consumed
- 40–70%: good — moderate mismatch, some export
- < 40%: poor — generation and demand poorly aligned

**Context note:** In dense urban environments with high-rise buildings, self-sufficiency above 30% is difficult because roof area is small relative to total floor area and demand. The LLM frames the result in context of building typology and urban density.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Self-sufficiency ratio with plain-language explanation of what it means
- Self-consumption ratio — how much of the generation is directly used vs exported
- Annual surplus (MWh exported to grid) and deficit (MWh imported from grid)
- Seasonal self-sufficiency: which season is the building most and least grid-dependent
- Typical daily time-match: when during the day demand exceeds generation and vice versa
- Note that electricity demand only is used — not thermal heating/cooling

**Visualization:** Three-part output:
1. Gauge chart showing self-sufficiency ratio (0–100%) with benchmark zones
2. Monthly self-sufficiency bar chart — shows seasonal grid dependency pattern
3. Typical day surplus/deficit area chart — shows hourly time-match on a representative day

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your BIPV system covers X% of annual electricity demand — the remaining Y% comes from the grid"
- One sentence on self-consumption: "Z% of generation is directly used on-site — the rest is exported"
- One sentence on worst season: "Grid dependency is highest in Winter when generation drops to X% of Summer levels"
- One sentence on daily pattern: "The biggest mismatch occurs between [hours] when demand peaks but generation has already dropped"

**Visualization:** Stacked annual energy flow diagram
- Shows: total demand / covered by BIPV / imported from grid
- Simple proportional bars — designed for client presentation

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of whether self-sufficiency meets project goals
- Three concrete improvement scenarios with estimated impact:
  1. Add more PV area (which surface, how much improvement)
  2. Add battery storage (size needed, hours of deficit covered)
  3. Reduce demand (efficiency measures impact on ratio)
- Whether the building type favours a self-consumption or export strategy
- If export: links to Basic Economic Signal skill — financial return depends on feed-in tariff
- If self-consumption focus: links to Demand vs Supply time-match detail

**Visualization:** Self-sufficiency improvement scenario chart
- Three bars: current / with additional PV / with battery storage
- Makes trade-offs immediately visible for design team discussion

---

## Common Pitfalls

- **Electricity demand only:** Self-sufficiency is calculated against electricity demand (`E_sys_MWhyr`) only — not total energy including heating and cooling. PV generates electricity, which cannot directly offset thermal demand. Always state this clearly.
- **Self-sufficiency ≠ self-consumption:** These are different metrics that architects often confuse. Self-sufficiency = demand covered by PV. Self-consumption = generation that is directly used. A building can have high self-consumption but low self-sufficiency. Always define both clearly.
- **District aggregation smooths mismatch:** At district scale, surpluses in one building offset deficits in another — making aggregate self-sufficiency higher than any individual building. Only realistic if a microgrid or shared connection exists.
- **Panel type affects ratio:** Different panel types have different efficiencies. If multiple types were simulated, compare self-sufficiency across types.

---

## References

- CEA4 PV and demand output documentation
- IDP 2025 Team 3: self-sufficiency ratio used as primary KPI (achieved 54–98% across building types)
- IDP 2024 Team 8: self-sufficiency and self-consumption calculated at district level
- Interview — Interviewee B: self-sufficiency and self-consumption both calculated manually as derived metrics
- Interview — Interviewee C: compared demand and production profiles to determine PV placement and sizing
