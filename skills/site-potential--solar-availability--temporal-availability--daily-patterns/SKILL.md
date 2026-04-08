---
name: site-potential--solar-availability--temporal-availability--daily-patterns
description: Use when the architect wants to understand how solar availability varies across a typical day or across days of the year. Reads CEA daily irradiation outputs to identify peak radiation days, low radiation days, and typical daily production profiles.
intent: Translate CEA's 365-day irradiation data into design-relevant insight about daily solar variability — identifying the best and worst performing days, typical seasonal day profiles, and what daily variation means for BIPV reliability.
type: component
position_in_tree: "Goal → Site Potential → Solar Availability → Temporal Availability → Daily Patterns"
---

## Purpose

Answer the question: **"How does solar availability vary from day to day, and what does a typical good vs. bad day look like for my BIPV system?"**

This skill reads CEA's daily irradiation output (365 rows, one per day) and identifies patterns in daily solar availability — peak days, low days, seasonal trends, and typical day profiles by month.

---

## CEA4 Integration

This skill runs as a CEA4 plugin. All data is read automatically via the CEA4 `InputLocator` — no manual file handling required.

**Location context** read automatically from the project weather file:
```python
locator.get_weather()  # → .epw file containing city, latitude, longitude
```

**Daily irradiation data** accessed via InputLocator:
```python
locator.get_solar_radiation_csv(period="daily")
# → solar_irradiation_daily.csv (365 rows, district level)
```

**Note on building scale:** CEA does not output a per-building daily file by default. For building-scale daily analysis, this skill aggregates from the hourly file (`solar_irradiation_hourly.csv`) grouped by date. The InputLocator handles this automatically.

---

## Data Sources

**Primary CEA files accessed via InputLocator:**

| Scale | File |
|-------|------|
| District | `solar_irradiation_daily.csv` (365 rows) |
| Cluster | `solar_irradiation_daily.csv` (district file, framed for cluster context) |
| Building | Aggregated from `solar_irradiation_hourly.csv` grouped by date |

**Columns used (opaque surfaces only):**
- `date` — calendar date (2009-01-01 to 2009-12-31)
- `period` — CEA day identifier (D_000 to D_364)
- `irradiation_roof[kWh]`
- `irradiation_wall_north[kWh]`
- `irradiation_wall_south[kWh]`
- `irradiation_wall_east[kWh]`
- `irradiation_wall_west[kWh]`

**Columns ignored:**
- `irradiation_window_*` — windows cannot have BIPV installed
- `hour_start`, `hour_end`, `nominal_hours`, `coverage_ratio` — metadata only

**Key data observed (from case study):**
- 365 daily rows, date range 2009-01-01 to 2009-12-31
- Roof irradiation ranges from ~6,500 kWh (cloudy winter day) to ~57,000+ kWh (peak summer day)
- Significant day-to-day variation due to cloud cover — not just seasonal trend

---

## Scale Behaviour

**District scale:**
- Uses `solar_irradiation_daily.csv` directly
- Computes daily totals, identifies peak and low days, plots full year profile
- Framing: "Across the district, the best day generates X times more radiation than the worst"

**Cluster scale:**
- Uses district daily file as proxy — per-cluster daily files not available in CEA
- Framing adjusted: "District-wide daily patterns are representative of your cluster's solar exposure"
- Flags this limitation clearly in the output

**Building scale:**
- Aggregates hourly file by date for the specific building
- Shows that building's daily profile across the year
- Framing: "For building B1000, peak daily irradiation occurs in [month] reaching X kWh"

---

## Benchmark

**Daily irradiation quality thresholds (roof, district level):**
- > 40,000 kWh/day: high radiation day — strong BIPV output
- 15,000–40,000 kWh/day: moderate — useful but not peak
- < 15,000 kWh/day: low radiation day — minimal BIPV contribution

**Variability indicator:**
- Count of days above 40,000 kWh threshold gives a reliable estimate of high-output days per year
- In Shanghai climate: expect approximately 80–100 high-output days, concentrated in May–August

**Context note:** The LLM reads city from the weather file and adjusts benchmark framing accordingly — a Nordic city would have a very different distribution than Shanghai.

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- The peak day and its date/value
- The lowest day and its date/value
- The ratio between peak and lowest day
- Count of days above the high-output threshold
- Plain-language explanation of what drives day-to-day variation (cloud cover, day length, season)

**Visualization:** Full-year daily irradiation line chart
- X axis: Jan → Dec (365 days)
- Y axis: daily irradiation (kWh)
- Roof shown as primary line
- Threshold line at 40,000 kWh marked
- Source data shown below chart

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Your system has approximately X high-output days per year, concentrated between [months]"
- One sentence on the peak month
- One sentence on reliability — how many days fall below useful output threshold

**Visualization:** Monthly average bar chart
- X axis: Jan–Dec
- Y axis: average daily irradiation per month (kWh)
- Cleaner than the full 365-day chart — easier to read in a presentation
- Highlights peak month clearly

---

### If "Design implication" selected:
**What the LLM produces:**
- Recommendation on whether daily variability is a concern for this project's energy strategy
- If high variability: flag that storage or grid connection is important to smooth output
- If concentrated peak season: recommend sizing BIPV for peak performance and accepting low-season grid dependency
- Links to Demand vs Supply skill if demand-matching analysis would be useful

**Visualization:** Good day vs bad day profile comparison
- Two overlaid daily profiles (representative peak day vs representative low day)
- X axis: hour of day (0–24)
- Y axis: hourly irradiation (kWh)
- Makes the difference between a good and bad solar day immediately visible

---

## Common Pitfalls

- **Day-to-day noise is normal:** Large swings between adjacent days are due to cloud cover and are expected — do not flag individual low days as problems. Look at monthly averages and counts of good days instead.
- **Date context matters:** The CEA file uses a reference year (2009 in this dataset) — this is a typical meteorological year, not a forecast. Frame it as representative, not predictive.
- **District vs building:** Daily per-building data is not directly available from CEA — always flag this when the architect selects building scale, and explain that the hourly aggregation is used instead.

---

## References

- CEA4 solar irradiation output documentation
- IDP 2024 Team 8: daily and seasonal PV production analysis used to evaluate panel type selection
- IDP 2025 Team 3: daily demand vs PV potential charts used to justify orientation decisions
- Interview — Interviewee C: "We looked at production depending on orientation, time (daily/seasonal)"
- Interview — Interviewee D: "I would want hourly production (e.g. weekly profiles)"
