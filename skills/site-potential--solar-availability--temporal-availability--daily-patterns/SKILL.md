---
name: site-potential--solar-availability--temporal-availability--daily-patterns
description: Use when the architect wants to understand the short-term, hour-of-day solar availability pattern for BIPV. Reads hourly CEA solar irradiation outputs and compares average 24-hour profiles by opaque surface.
intent: Show how solar availability shifts across a typical day, which surfaces provide morning, midday, and afternoon production, and whether the daily profile suggests short-term storage or demand-shifting pressure.
type: component
position_in_tree: "Goal → Site Potential → Solar Availability → Temporal Availability → Daily Patterns"
---

## Purpose

Answer the question: **"How does solar availability change across a typical day, and what does that mean for short-term storage or load matching?"**

This is the short-term temporal availability skill. It should not describe the whole 365-day profile. It uses `solar_irradiation_hourly.csv` to calculate an average 24-hour profile for each opaque surface:

- roof
- south wall
- east wall
- west wall
- north wall

The key design value is timing. Roofs usually peak around midday, east facades support morning generation, and west facades support afternoon generation. A flatter profile can reduce short-term battery pressure and improve direct self-consumption.

---

## Data Used

Primary file:
- `solar_irradiation_hourly.csv`

Columns:
- `date` or hour column, used to extract hour of day from 00:00 to 23:00
- `irradiation_roof[kWh]`
- `irradiation_wall_south[kWh]`
- `irradiation_wall_east[kWh]`
- `irradiation_wall_west[kWh]`
- `irradiation_wall_north[kWh]`

Ignored:
- `irradiation_window_*`, because windows are not BIPV panel surfaces
- metadata columns such as `hour_start`, `hour_end`, `coverage_ratio`

Required calculation:
```
average_hourly_irradiation[hour, surface] =
mean(irradiation_surface[kWh] for all rows with the same hour of day)
```

---

## What Python Should Calculate

Do this before calling the LLM:

- average hourly profile from 00:00 to 23:00 for every opaque surface
- peak hour and peak value for each surface
- active generation window for each surface
- which surface supports morning production best
- which surface supports afternoon production best
- which combination of surfaces gives the smoothest daily profile
- short-term mismatch indicator, if hourly demand or PV generation is available

Do not ask the LLM to infer these values from raw CSV rows.

---

## LLM Role

The LLM should interpret the computed profile:

- whether the daily profile is concentrated or spread across the day
- whether roof-only generation creates a sharp midday peak
- whether east/west facades help smooth the profile
- whether short-term battery storage or load shifting may be useful
- what this means for BIPV placement in architectural terms

The LLM should not claim a precise battery size unless hourly demand and hourly PV generation are provided.

---

## Output Expectations

**Key takeaway**
- Start with the strategy answer: which surface combination gives the most constant daily profile.
- State whether short-term storage is likely needed, not needed, or cannot be sized from irradiation alone.
- Mention the main design implication, such as roof-first with east/west facade support for morning/afternoon smoothing.

**Explain the numbers**
- Explain the chart values: peak hour, peak surface, active generation windows, morning/afternoon contributors.
- Explain why the recommended surface mix is smoother than roof-only.
- State clearly that this chart is an average 24-hour profile, not a plot of every hour in the year.

**Design implication**
- Connect daily production timing to building use type when use-type data is available.
- For daytime-heavy uses, favour direct self-consumption and load matching.
- For residential or evening-heavy uses, flag stronger short-term storage or demand-shifting pressure.
- Suggest which surfaces should be considered for PV coverage, but only size coverage if area, WWR, and PV generation data are available.

---

## Common Pitfalls

- Do not plot or discuss hour-of-year as hour-of-day. The x-axis should be 00:00 to 23:00.
- Do not use `solar_irradiation_daily.csv` for this skill; daily totals collapse timing information.
- Do not size storage from irradiation alone. Storage sizing needs hourly PV generation and hourly demand.
- Do not recommend low-performing facades only for smoothness. Timing helps choose among viable surfaces, but it does not rescue a surface with very weak solar availability.

## References

- CEA4 solar irradiation output documentation
- IDP 2024 Team 8: daily and seasonal PV production analysis used to evaluate panel type selection
- IDP 2025 Team 3: daily demand vs PV potential charts used to justify orientation decisions
- Interview — Interviewee C: "We looked at production depending on orientation, time (daily/seasonal)"
- Interview — Interviewee D: "I would want hourly production (e.g. weekly profiles)"
