---
name: site-potential--contextual-feasibility--basic-economic-signal
description: Use when the architect wants to understand the basic economic context for BIPV in their project location before running detailed financial analysis. Uses location from CEA weather file and internet search to retrieve current electricity prices, grid carbon intensity, and market context.
intent: Give the architect a quick economic orientation before committing to BIPV — covering local electricity prices, grid carbon intensity, typical BIPV installation costs, and whether the market context makes BIPV economically compelling or marginal in this location.
type: component
position_in_tree: "Goal → Site Potential → Contextual Feasibility → Basic Economic Signal"
---

## Purpose

Answer the question: **"How does the local energy market context shape the economic case for BIPV?"**

This skill provides a high-level economic orientation for BIPV in the project location — not a detailed financial analysis (that is handled by the Impact & Viability skills), but a quick signal on whether the economic context is favourable, marginal, or challenging for BIPV investment.

This is a **pre-design** skill — it helps the architect understand the economic environment before running simulations, so they can frame expectations with clients early.

---

## CEA4 Integration

This skill runs as a CEA4 plugin.

**Location context** read automatically from the project weather file:
```python
locator.get_weather()
# → .epw file → extracts city, country, latitude, longitude
# This location is passed directly to the internet search
```

**No CEA simulation data is used by this skill.** All information comes from internet search based on the project location.

---

## Data Sources

**Primary source: Internet search**

The LLM performs targeted searches for the project location using the following queries:
- `"[city] electricity price residential commercial [current year]"`
- `"[country] grid carbon intensity electricity [current year]"`
- `"[country] BIPV installation cost per m2 [current year]"`
- `"[country] solar PV payback period typical [current year]"`
- `"[city] feed-in tariff rate solar [current year]"`

**Key information retrieved:**
- Current residential and commercial electricity price (local currency per kWh)
- Grid carbon intensity (kgCO2/kWh) — how clean or dirty is the local grid
- Typical BIPV installation cost range per m² for the market
- Typical simple payback period for solar in this location
- Whether electricity prices are trending up or down

**Source quality:** The LLM prioritises national energy agency statistics, utility company published tariffs, and reputable energy research organisations. It flags when information may be outdated and provides the source and date.

---

## Scale Behaviour

Basic economic signal is a **location-level** analysis — the same economic context applies regardless of scale. Scale affects framing only:

**District scale:**
- Highlights that district-scale installations may benefit from economies of scale
- Flags any bulk procurement or district energy scheme incentives

**Cluster scale:**
- Notes that shared infrastructure across a cluster may reduce per-building connection costs

**Building scale:**
- Focuses on single-building economics
- Highlights any size thresholds that affect eligibility for incentives

---

## Benchmark

**Economic signal interpretation:**

| Indicator | Strong case | Marginal case | Weak case |
|-----------|-------------|---------------|-----------|
| Electricity price | > 0.20 €/kWh | 0.10–0.20 €/kWh | < 0.10 €/kWh |
| Grid carbon intensity | > 0.4 kgCO2/kWh | 0.2–0.4 kgCO2/kWh | < 0.2 kgCO2/kWh |
| Typical payback | < 8 years | 8–15 years | > 15 years |
| Price trend | Rising | Stable | Falling |

**Context note:** Low electricity prices (like Shanghai at ~0.08 yuan/kWh in 2024) create a weak economic case for BIPV from a pure cost-saving perspective — but a strong carbon case if the grid is carbon-intensive. The LLM always presents both dimensions separately so the architect can make an informed argument for whichever is more relevant to their client.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Current electricity price for the location with source and date
- Grid carbon intensity with source and date
- Typical BIPV installation cost range for the market
- Typical payback period range for the location
- Whether electricity prices are trending up or down

**Visualization:** Economic context dashboard
- Four key indicators shown as a simple scorecard
- Strong / Marginal / Weak per indicator
- Source links listed below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: overall economic signal for the location
- The dominant argument for BIPV in this context — is it economic, carbon-driven, or regulatory?
- One sentence on the biggest economic risk or opportunity

**Visualization:** Signal summary card
- Overall signal (Strong / Marginal / Weak)
- Primary argument (Economic / Carbon / Regulatory)
- Designed to be used in early client conversation

---

### If "Design implication" selected:
**What the LLM produces:**
- Concrete recommendation on how to frame the BIPV case for this location
- If strong economic case: lead with financial return argument
- If weak economic case but strong carbon case: lead with sustainability and carbon narrative
- If both weak: flag that the BIPV case may need to rest on architectural quality and regulatory compliance
- Sizing recommendation: in weak economic contexts, recommend right-sizing for self-consumption only rather than export
- Links to LCOE and Carbon Payback skills for detailed financial and carbon analysis

**Visualization:** Argument framing diagram
- Three argument tracks: Economic / Carbon / Architectural
- Strength of each track for this location indicated
- Helps architect choose the right narrative for their client

---

## Common Pitfalls

- **Electricity prices vary by tariff:** Commercial and residential tariffs differ significantly in most countries. Always retrieve both and flag which applies to the project building type.
- **Grid carbon intensity changes over time:** As grids decarbonise, the carbon argument for BIPV weakens. Always note the trend direction alongside the current value.
- **Currency conversion:** Installation costs and electricity prices are in local currency — always note the currency and approximate EUR/USD equivalent for international comparison.
- **This is not financial advice:** Always include a note that this is an early orientation only and detailed financial analysis should be done by a qualified energy consultant.

---

## References

- CEA4 weather file location extraction
- IDP 2024 Team 8: noted that Shanghai electricity prices (~0.3–0.6 yuan/kWh) made PV economics challenging — grid carbon intensity was the stronger argument
- IDP 2024 Team 2: used Chinese grid carbon intensity (0.45 kgCO2/kWh) as key input for LCA analysis
- Interview — Interviewee B: wanted "scenario suggestions based on context — climate, policy, etc."
- Interview — Interviewee C: "Electricity in China is relatively cheap — it doesn't always make sense to install PV on every surface"
