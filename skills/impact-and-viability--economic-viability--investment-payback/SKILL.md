---
name: impact-and-viability--economic-viability--investment-payback
description: Use when the architect wants to understand how long it takes for a BIPV investment to pay back its installation cost through energy savings and export revenue. Combines CEA PV yield data with internet-sourced cost and tariff information.
intent: Give the architect a clear timeline for when their BIPV investment breaks even — and what the cumulative financial benefit looks like over the system's lifetime — so they can make an informed case to clients and developers.
type: component
position_in_tree: "Goal → Impact and Viability → Economic Viability → Investment Payback"
---

## Purpose

Answer the question: **"How long until my BIPV investment pays back — and what is the financial return over its lifetime?"**

This skill calculates the simple payback period and cumulative financial return for the BIPV system — combining CEA's generation data with local electricity prices and installation costs to give the architect a time-based financial picture.

It covers:
- **Simple payback period** — years until installation cost is recovered
- **Cumulative return** — total financial benefit over 25-year lifetime
- **Sensitivity to electricity price trends** — how rising prices affect payback

---

## CEA4 Integration

This skill runs as a CEA4 plugin.

**Location context** read automatically from project weather file:
```python
locator.get_weather()  # → city, country, latitude, longitude
```

**PV yield data** accessed via InputLocator:
```python
locator.get_pv_results(panel_type="PV1")
# → PV_PV{n}_total_buildings.csv
# Key columns: E_PV_gen_kWh (annual), area_PV_m2 (installed area)
```

**Self-consumption data** from Self Sufficiency skill output:
- `self_consumed_kWh` — generation directly used on-site (saves grid electricity cost)
- `exported_kWh` — generation exported to grid (earns feed-in tariff if available)

**No CEA financial data available** — installation costs, electricity prices and tariffs retrieved via internet search.

---

## Data Sources

**From CEA (via InputLocator):**
- `E_PV_gen_kWh` — annual generation per panel type
- `area_PV_m2` — installed area
- Self-consumption split from demand/PV alignment calculation

**From Internet search:**
- Installation cost per m² (local market)
- Grid electricity price (local tariff)
- Feed-in tariff rate (if available)
- Historical electricity price trend (annual % increase)
- Available subsidies or grants

---

## Calculation

**Simple Payback Period:**
```
annual_savings = self_consumed_kWh × grid_electricity_price
annual_export_revenue = exported_kWh × feed_in_tariff (if available)
annual_benefit = annual_savings + annual_export_revenue

installation_cost = area_PV_m2 × cost_per_m2 (from internet search)
effective_cost = installation_cost × (1 - subsidy_rate)

simple_payback_years = effective_cost / annual_benefit
```

**Cumulative Return (25-year lifetime):**
```
For each year y (1 to 25):
  electricity_price_y = grid_price × (1 + annual_price_increase)^y
  annual_benefit_y = self_consumed_kWh × electricity_price_y + export_revenue_y
  cumulative_benefit_y = sum of annual_benefit from year 1 to y

net_lifetime_return = cumulative_benefit_25 - effective_installation_cost
```

**Three scenarios calculated:**
1. Current electricity price (flat, no increase)
2. Electricity price rising 2% per year
3. Electricity price rising 5% per year (high energy cost scenario)

---

## Scale Behaviour

**District scale:**
- Total investment and aggregate payback for district-wide installation
- Framing: "A district-wide BIPV investment of X would pay back in Y years under current electricity prices"

**Cluster scale:**
- Per-building payback periods within cluster
- Identifies best and worst financial performers

**Building scale:**
- Single building payback with scenario analysis
- Most useful for individual client conversations
- Framing: "Building B1000's BIPV investment of X pays back in Y years — generating Z in net return over 25 years"

---

## Benchmark

**Simple payback period:**
- < 8 years: strong investment — well within panel lifetime
- 8–15 years: acceptable — positive return over lifetime
- 15–20 years: marginal — limited return, relies on panel longevity
- > 20 years: weak — unlikely to recover investment within panel lifetime

**Context note:** In markets with low electricity prices (e.g. China, parts of the Middle East), payback periods tend to be longer. Rising electricity prices significantly improve the economics — the 5% scenario is particularly relevant for markets where energy prices are expected to increase due to carbon pricing or grid decarbonisation policy.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Installation cost estimate with source and date
- Annual savings from self-consumption
- Annual export revenue (if feed-in tariff available)
- Simple payback period under current prices
- Cumulative return at year 10, 15, 20, 25
- All assumptions stated clearly

**Visualization:** Cumulative return chart
- X axis: years 0–25
- Y axis: cumulative financial return (currency)
- Three lines: flat price / +2% / +5% electricity price scenarios
- Payback crossover point marked for each scenario
- Installation cost shown as horizontal line

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your BIPV investment pays back in X years — returning Y over 25 years at current electricity prices"
- One sentence on how rising electricity prices improve the return
- One sentence on subsidy impact

**Visualization:** Payback period scenario comparison
- Three bars: current price / +2% / +5% scenarios
- Panel lifetime (25 years) marked
- Simple and client-ready

---

### If "Design implication" selected:
**What the LLM produces:**
- Assessment of whether payback period is acceptable for this project type and client
- If developer client: flag that payback > 10 years may reduce appetite — recommend subsidy strategy
- If owner-occupier: longer payback more acceptable — lifetime return is the relevant metric
- If electricity prices rising: recommend sizing system generously now while installation costs are relatively low
- If no feed-in tariff: recommend maximising self-consumption ratio rather than oversizing for export
- Links to Cost Analysis skill for LCOE context

**Visualization:** Investment decision matrix
- 2×2 matrix: payback period (short/long) vs electricity price trend (stable/rising)
- Project positioned on matrix
- Recommended strategy for each quadrant

---

## Common Pitfalls

- **Simple payback ignores time value of money:** For a more rigorous analysis, NPV (Net Present Value) should be used. The skill notes this and flags that simple payback underestimates the true return in high-inflation environments.
- **Export revenue depends on policy:** In markets without feed-in tariffs, exported electricity has zero financial value. Always check infrastructure readiness skill output before including export revenue.
- **Panel degradation not included:** PV panels lose approximately 0.5% efficiency per year. Over 25 years this reduces generation by ~12%. The skill notes this as a conservative adjustment factor.
- **This is not financial advice:** Always include a note that estimates are for early feasibility orientation only.

---

## References

- CEA4 PV output documentation
- IDP 2024 Team 8: payback period calculated per panel type — noted economic challenge in Shanghai low-price context
- IDP 2024 Team 2: future scenario analysis showing how grid decarbonisation affects long-term economics
- Interview — Interviewee B: calculated payback period manually as a missing CEA metric
- Interview — Interviewee C: questioned economic viability in Chinese context — this skill provides the evidence
