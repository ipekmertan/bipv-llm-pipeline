---
name: impact-and-viability--economic-viability--cost-analysis
description: Use when the architect wants to understand how the cost of their BIPV system compares to local electricity prices, including LCOE calculation, cost vs grid comparison, and available subsidies. Combines CEA PV yield data with internet-sourced cost and market information.
intent: Give the architect a clear picture of the economic cost of their BIPV system relative to the local energy market — from the cost per unit of electricity generated to how that compares to buying from the grid, and what financial incentives are available.
type: component
position_in_tree: "Goal → Impact and Viability → Economic Viability → Cost Analysis"
---

## Purpose

Answer the question: **"How does the cost of my BIPV-generated electricity compare to what I currently pay for grid electricity?"**

This skill bridges CEA's technical outputs with real-world financial context. It calculates the Levelised Cost of Energy (LCOE) — the true cost per kWh of electricity generated over the system's lifetime — and compares it to the local grid electricity price.

It covers:
- **LCOE** — lifetime cost per kWh generated
- **Cost vs grid** — is BIPV-generated electricity cheaper than buying from the grid?
- **Available subsidies** — what financial incentives reduce the effective cost?

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.

**PV yield data** accessed via InputLocator:
```python
locator.get_pv_results(panel_type="PV1")
# → PV_PV{n}_total_buildings.csv
# Key columns: E_PV_gen_kWh (annual generation), area_PV_m2 (installed area)
```

**No CEA financial data is available** — installation costs and electricity prices are retrieved via internet search based on project location.

---

## Data Sources

**From CEA (via InputLocator):**
- `E_PV_gen_kWh` — annual electricity generation per panel type (kWh/year)
- `area_PV_m2` — total installed PV area (m²)

**From Internet search (location-based):**
- BIPV installation cost per m² for the local market
- Local electricity price (residential and commercial tariffs)
- Available subsidies, feed-in tariffs, or tax incentives
- Typical O&M (operation and maintenance) cost per m²/year

---

## LCOE Calculation

```
LCOE = (installation_cost + lifetime_O&M_cost) / lifetime_generation

Where:
  installation_cost = area_PV_m2 × cost_per_m2 (from internet search)
  lifetime_O&M = area_PV_m2 × annual_O&M_per_m2 × panel_lifetime_years
  lifetime_generation = E_PV_gen_kWh × panel_lifetime_years
  panel_lifetime = 25 years (standard assumption)

Units: currency/kWh (same as local electricity price for direct comparison)
```

**Subsidy adjustment:**
```
effective_installation_cost = installation_cost × (1 - subsidy_rate)
adjusted_LCOE = (effective_installation_cost + lifetime_O&M) / lifetime_generation
```

**Cost vs grid comparison:**
```
savings_per_year = self_consumed_kWh × grid_electricity_price
export_revenue_per_year = exported_kWh × feed_in_tariff_rate (if available)
total_annual_benefit = savings_per_year + export_revenue_per_year
```

---

## Scale Behaviour

**District scale:**
- Total installation cost estimate for district-wide BIPV
- District LCOE based on aggregate generation and area
- Framing: "A district-wide BIPV installation of X m² would cost approximately Y — generating electricity at Z per kWh vs the local grid price of W per kWh"

**Cluster scale:**
- Cluster-level cost and LCOE
- Per-building cost breakdown showing which buildings drive the total investment

**Building scale:**
- Single building installation cost and LCOE
- Most useful for client conversations about individual building investment

---

## Benchmark

**LCOE vs grid price:**
- LCOE < grid price: BIPV is cost-competitive — strong economic argument
- LCOE 1–1.5× grid price: marginal — borderline economic case
- LCOE > 1.5× grid price: not cost-competitive — carbon or architectural argument should lead

**Typical LCOE ranges (from IDP project data, Shanghai context):**
- CdTe panels: lowest LCOE due to low installation cost
- Monocrystalline: moderate LCOE — higher cost but higher efficiency
- Context note: Shanghai electricity prices (~0.08–0.15 yuan/kWh) are low — making BIPV economic case challenging without subsidies

**Subsidy impact:**
- Even a 20–30% subsidy can shift BIPV from marginal to cost-competitive in many markets
- The LLM always calculates both subsidised and unsubsidised LCOE for comparison

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Total estimated installation cost with source and date
- LCOE per kWh with calculation shown transparently
- Local grid electricity price with source and date
- LCOE vs grid price comparison
- Available subsidies and their impact on effective LCOE
- Panel type LCOE comparison if multiple types simulated
- Note on all assumptions made

**Visualization:** LCOE vs grid price comparison chart
- Bar chart: LCOE per panel type vs local grid price
- Subsidy-adjusted LCOE shown as overlay
- Makes cost-competitiveness immediately visible

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "BIPV-generated electricity costs X per kWh vs Y per kWh from the grid — [cheaper/more expensive] by Z%"
- One sentence on subsidy impact
- One sentence on which panel type is most cost-competitive

**Visualization:** Simple cost comparison card
- Three values: LCOE / adjusted LCOE with subsidy / grid price
- Colour coded: green if BIPV cheaper, amber if marginal, red if more expensive

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of the economic case strength for this project and location
- If cost-competitive: recommend leading with financial return argument in client presentation
- If marginal: recommend combining with carbon argument and long-term energy price trend
- If not competitive: recommend focusing on self-consumption only (avoid oversizing for export)
- Recommendation on which panel type offers best economic case
- Links to Investment Payback skill for timeline perspective
- Links to Basic Economic Signal for broader market context

**Visualization:** Economic argument strength dashboard
- Three indicators: LCOE vs grid / subsidy availability / price trend direction
- Overall economic signal: Strong / Marginal / Weak
- Designed for early client conversation

---

## Common Pitfalls

- **Installation costs vary enormously:** BIPV facade costs can be 3–5× higher than standard rooftop PV due to integration complexity. Always distinguish between roof and facade installation costs.
- **Currency and units:** Always state currency and convert to EUR/USD equivalent for international comparison. Electricity prices in yuan/kWh need conversion for context.
- **O&M costs are often overlooked:** Over 25 years, maintenance costs add significantly to total lifetime cost. Always include them in LCOE.
- **This is not financial advice:** Always include a note that estimates are for early feasibility orientation and should be verified with a local quantity surveyor or energy consultant.

---

## References

- CEA4 PV output documentation (for generation and area data)
- IDP 2024 Team 8: LCOE calculated per panel type per building — CdTe found most cost-effective
- IDP 2024 Team 2: economic analysis showing BIPV not cost-competitive vs Shanghai grid without subsidies
- Interview — Interviewee B: calculated LCOE manually as a derived metric not available in CEA
- Interview — Interviewee C: "Electricity in China is cheap — it doesn't always make sense economically"
