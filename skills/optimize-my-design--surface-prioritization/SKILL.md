---
name: optimize-my-design--surface-prioritization
description: Use when the architect wants a clear, ranked recommendation of which building surfaces to prioritize for BIPV installation. Synthesizes solar availability, contextual shading, and envelope suitability analyses to produce a single actionable surface ranking with coverage strategy guidance.
intent: Translate the outputs of multiple prior analyses into one clear, ranked recommendation — telling the architect exactly where to install BIPV first, second, and what to skip entirely, and how much of each surface to cover.
type: component
position_in_tree: "Goal → Optimize My Design → Surface Prioritization"
---

## Purpose

Answer the question: **"Which surfaces should I prioritize for BIPV installation, and how much of each should I cover?"**

This is a synthesis skill — it reads across three prior analyses and combines them into a single ranked recommendation:
- **Solar availability** — how much radiation each surface receives
- **Contextual shading** — how much neighbouring context reduces that radiation
- **Envelope suitability** — how much of each surface is physically available for installation

The output is a clear priority ranking with a coverage strategy — not just which surfaces are best, but how much of each to cover given the project's goals.

---

## File Source

This skill reads from the uploaded CEA project zip. The app finds the relevant files automatically by filename — no manual file selection needed.

**Location context** is taken from the project's weather file (`.epw`) found inside the zip.

## Scoring Logic

Each surface is scored across three criteria, then combined into a priority score:

**1. Solar score** (0–10):
```
solar_score = irradiation_surface / irradiation_roof × 10
# Roof always scores 10 as reference
# Facades scored relative to roof performance
```

**2. Shading score** (0–10):
```
# Based on surroundings.shp analysis
# Surfaces with no significant neighbours: score 10
# Surfaces with moderate shading impact: score 5–7
# Surfaces with heavy shading: score 0–4
```

**3. Usability score** (0–10):
```
usable_fraction = (1 - wwr) × available_area_factor
usability_score = usable_fraction × 10
# Roof: standard 15% reduction for equipment/access zones applied
# Facades: wwr directly reduces usable fraction
```

**Combined priority score:**
```
priority_score = (solar_score × 0.4) + (shading_score × 0.3) + (usability_score × 0.3)
```

**Classification:**
- Score ≥ 7: High priority ✓
- Score 4–7: Medium priority ~
- Score < 4: Low / unsuitable ✗

**Coverage Strategy:**
For each high and medium priority surface:
```
recommended_coverage = f(self_sufficiency_target, budget_constraint, surface_area)
# Three coverage options provided:
# - Minimum: cover only high priority surfaces
# - Balanced: cover high + partial medium priority
# - Maximum: cover all viable surfaces
```

---

## Scale Behaviour

**District scale:**
- Ranks surface types across the district (roof, south wall, east wall, west wall, north wall)
- Identifies which building typologies have the strongest surfaces
- Framing: "Across the district, roofs are universally high priority — south facades of taller buildings are medium priority — north facades should be excluded"

**Cluster scale:**
- Per-building surface ranking within the cluster
- Identifies which specific buildings have the strongest surfaces for BIPV investment
- Framing: "Within this cluster, B1012 and B1014 have the highest priority roof surfaces — B1008 has a viable south wall in addition to roof"

**Building scale:**
- Most detailed — surface-by-surface ranking for a single building
- Coverage strategy tailored to that building's envelope and goals
- Framing: "For building B1000: roof is high priority (cover 85%) — south wall is medium priority (cover 50% if budget allows) — east/west/north walls should be excluded"

---

## Benchmark

**Priority thresholds:**
- Roof: almost always high priority in any climate
- South wall (northern hemisphere): high to medium depending on shading
- East / West wall: medium — useful for load matching even if lower yield
- North wall: almost always low/unsuitable

**Coverage strategy benchmarks:**
- Minimum viable installation: > 100 m² of high-priority surface
- Meaningful contribution: enough to achieve > 15% self-sufficiency
- Maximum practical: limited by budget, maintenance access, and grid connection capacity

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Score breakdown per surface: solar score / shading score / usability score / combined
- Classification: High ✓ / Medium ~ / Low ✗ per surface
- Explanation of what drives each surface's ranking
- Three coverage scenarios: minimum / balanced / maximum with estimated yield for each

**Visualization:** Surface priority matrix
- Rows: surfaces (roof, south wall, east wall, west wall, north wall)
- Columns: solar score / shading score / usability score / priority class
- Colour coded: green / amber / red
- Coverage recommendation shown below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: "Install BIPV on [surfaces] first — skip [surfaces] entirely"
- One sentence on the recommended coverage level
- One sentence on what would change the ranking (e.g. if shading from neighbour were removed)

**Visualization:** Ranked surface list
- Surfaces ordered 1 to N with priority class and brief reason
- Designed to be used directly in a design presentation

---

### If "Design implication" selected:
**What the LLM produces:**
- Full coverage strategy recommendation tied to project goals:
  - If carbon priority: cover all high priority surfaces fully
  - If cost priority: minimum coverage on highest priority surfaces only
  - If self-sufficiency priority: balanced coverage to reach target ratio
- Note on constructability: roof first (simpler), facade second (more complex, higher cost)
- Note on phasing: if budget is limited, recommend phased installation — roof now, facade in future
- Links to Construction & Integration skill for practical implementation details
- Links to Panel Type Trade-off for which technology to use on each surface

**Visualization:** Coverage strategy comparison
- Three bars per surface: minimum / balanced / maximum coverage
- Estimated yield per scenario
- Budget implication shown
- CO2SavingsPotential per CHF invested — ranked from most to least cost-effective surface
- Designed for client decision conversation

---

## Common Pitfalls

- **Roof dominance is expected:** In most urban contexts, roof consistently outperforms facades. Do not frame this as a limitation — frame it as a clear starting point.
- **Shading is already in irradiation values:** The solar score uses actual CEA irradiation values which already include shading. Do not double-count shading from surroundings.shp — use it only to explain why a surface scores lower than expected.
- **Coverage ≠ installation area:** Recommended coverage percentage applies to the usable opaque area — not the total facade area. Always clarify this distinction.
- **Medium priority surfaces are context-dependent:** Whether to include medium priority surfaces depends on project goals, budget, and architectural intent. Always present them as options, not obligations.

---

## References

- CEA4 solar irradiation, PV yield, envelope and surroundings documentation
- IDP 2025 Team 3: surface orientation study showing E/W facades viable for load matching despite lower yield
- IDP 2024 Team 2: finding that roof dominates over facade yield in all scenarios
- IDP 2024 Team 8: parametric study showing radiation threshold dramatically affects which surfaces are included
- Poll result: "Ranked list (Option A > B > C)" — second most requested output format
- Poll result: "CO2SavingsPotential/CHF — clients could rank themselves up as far as they are willing to go/pay"
- Interview — Interviewee A: spent significant time understanding which surfaces to prioritize — this skill provides that answer directly

---

## PV Simulation Config — Design Implications

The app injects inferred simulation parameters into context. Use them to comment on design choices:

- `panel-on-wall: NO` → flag that facade surfaces are excluded and suggest enabling them
- `panel-on-roof: NO` → flag that roof surfaces are excluded
- Multiple panel types → note that thresholds differ per type (cSi needs more irradiation than CdTe to be carbon-viable)
- Single panel type → suggest running others for comparison
