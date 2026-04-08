---
name: site-potential--contextual-feasibility--infrastructure-readiness
description: Use when the architect wants to understand how the local grid infrastructure supports BIPV integration in their project location. Uses location from CEA weather file and internet search to retrieve current grid readiness information for that city and country.
intent: Give the architect a clear picture of the infrastructure context before committing to BIPV — covering grid capacity, feed-in tariff availability, net metering policies, and connection requirements for the project location.
type: component
position_in_tree: "Goal → Site Potential → Contextual Feasibility → Infrastructure Readiness"
---

## Purpose

Answer the question: **"How prepared is the local grid infrastructure to support BIPV in this location?"**

This skill uses the project location (read automatically from the CEA weather file) to search for current information about the local electricity grid's readiness to accept BIPV-generated power. It covers grid capacity, feed-in policies, net metering availability, and connection requirements.

This is a **pre-design** skill — it gives the architect the infrastructure context they need before committing to a BIPV strategy, not after running simulations.

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
- `"[city] BIPV grid connection requirements [current year]"`
- `"[country] net metering solar feed-in tariff policy [current year]"`
- `"[city] electricity grid capacity renewable energy [current year]"`
- `"[country] BIPV building integrated photovoltaics regulations [current year]"`

**Key information retrieved:**
- Whether net metering or feed-in tariffs are available
- Grid connection process and typical timeline
- Any capacity limits on distributed solar generation
- Whether the local utility actively supports or restricts small-scale solar
- Current grid carbon intensity (relevant for carbon impact analysis)

**Source quality:** The LLM prioritises government energy agency websites, national grid operator publications, and reputable energy research organisations. It flags when information may be outdated and provides the source and date of each piece of information.

---

## Scale Behaviour

Infrastructure readiness is a **location-level** analysis — it applies equally to district, cluster, and building scale since it reflects the policy and grid context of the city/country, not individual buildings.

The scale selection affects only the framing:

**District scale:**
- Framing: "For a district-scale BIPV installation in [city], the key infrastructure considerations are..."
- Highlights capacity limits that may apply to large aggregated systems

**Cluster scale:**
- Framing: "For a cluster of buildings in [city], the connection and metering arrangements would typically involve..."

**Building scale:**
- Framing: "For a single building BIPV installation in [city], the process would typically be..."
- Highlights individual building connection requirements

---

## Benchmark

**Infrastructure readiness indicators:**

| Indicator | Strong | Moderate | Weak |
|-----------|--------|----------|------|
| Net metering | Available, no cap | Available, with cap | Not available |
| Feed-in tariff | Active, competitive rate | Available, low rate | Not available |
| Grid capacity | No restrictions | Local restrictions | Widespread curtailment |
| Connection process | Streamlined, < 3 months | Standard, 3–6 months | Complex, > 6 months |

The LLM maps retrieved information onto these indicators and gives an overall readiness rating for the location.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Current net metering and feed-in tariff status for the location
- Grid connection process overview and typical timeline
- Any capacity restrictions or curtailment risks
- Current grid carbon intensity (kgCO2/kWh) — relevant for carbon impact analysis
- Source and date for each piece of information

**Visualization:** Infrastructure readiness scorecard
- Four indicators shown as a simple traffic light grid
- Green / Amber / Red per indicator
- Source links listed below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: overall infrastructure readiness rating for the location
- Two or three key facts the architect needs to know before proceeding
- Any critical blockers or strong enablers

**Visualization:** Summary card
- Overall rating (Strong / Moderate / Weak)
- Three bullet points of key facts
- Designed to be shared with a client or included in a feasibility report

---

### If "Design implication" selected:
**What the LLM produces:**
- Concrete recommendation on how infrastructure context should shape the BIPV strategy
- If net metering is available: recommend sizing for self-consumption + export
- If no feed-in tariff: recommend sizing purely for self-consumption to maximise financial return
- If grid capacity is constrained: recommend battery storage consideration
- If connection process is long: flag timeline implications for project delivery
- Links to Basic Economic Signal skill for financial context

**Visualization:** Strategy recommendation card
- Three scenario options based on infrastructure context
- Each option with a brief rationale
- Designed to support early client conversation

---

## Common Pitfalls

- **Policies change frequently:** Grid policies and feed-in tariffs change often — always display the date of retrieved information and encourage the architect to verify with local authorities before making financial commitments.
- **City vs national policy:** In some countries (e.g. China, USA), grid policy varies significantly by city or province. Always search at city level first, then national level, and flag any discrepancy.
- **Language barrier:** In non-English-speaking countries, the most authoritative sources may be in the local language. The LLM notes when translation was involved and flags lower confidence accordingly.
- **This is not legal or financial advice:** Always include a note that this information is for early feasibility orientation only and should be verified with a local energy consultant or utility before project commitment.

---

## References

- CEA4 weather file location extraction
- Interview — Interviewee B: "Scenario suggestions based on context — climate, policy, etc." as desired AI capability
- Interview — Interviewee D: used grid carbon intensity and policy context in scenario analysis
- IDP 2024 Team 8: noted that Shanghai electricity prices made PV economics challenging — grid policy context was critical to their analysis
