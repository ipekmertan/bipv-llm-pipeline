---
name: site-potential--contextual-feasibility--regulatory-constraints
description: Use when the architect wants to understand planning rules, permits, approval risks, height limits, heritage restrictions, or facade/roof BIPV regulatory constraints for the project location.
intent: Turn location-specific planning and regulatory context into early BIPV design constraints: where BIPV is likely straightforward, where it may require approval, and what the architect should reserve or document before the concept becomes fixed.
type: component
position_in_tree: "Goal -> Site Potential -> Contextual Feasibility -> Regulatory Constraints"
---

## Purpose

Answer the question: **"What planning or regulatory constraints could affect BIPV in this project location?"**

This is a concept-stage regulatory brief for architects. It is not legal advice and it must not invent parcel-specific rules, but it should still give a useful early direction instead of returning an empty answer.

---

## App Integration

This skill runs inside the BIPV Analyst web app, not inside CEA4.

The user uploads a zipped CEA output scenario. The app extracts the project location from the weather file and may provide building heights from `zone_geometry.csv` when available. CEA does not contain local planning law; it only supplies project-side context such as location and height.

---

## Data Sources

Use only regulatory context supplied by the app: preloaded regional context and lightweight public web research summaries.

The search focus is:
- `[city] photovoltaic facade building permit planning permission`
- `[city] solar panels building regulations heritage conservation area`
- `[city] building height limit zoning photovoltaic roof solar`
- `[city] zoning building height limit roof equipment photovoltaic`
- `[city] mandatory solar photovoltaic new buildings building code`
- `[country] photovoltaic facade roof permit building regulations`
- `[region] BIPV facade regulations reflectivity glare building permit`

Key information to use:
- Whether roof PV or facade-integrated PV usually needs a permit
- Whether street-facing facades, heritage areas, conservation zones, or aesthetic review may restrict BIPV
- Whether roof-mounted equipment can affect building height limits
- Whether mandatory PV or solar-ready rules exist for new buildings or major renovations
- Which authority or official website is relevant

Source quality:
- Prefer local planning/building authority pages, national building or energy agencies, official code portals, and utility/public authority sources.
- If a source is broad or non-local, label it clearly.
- Always include website addresses for the sources used.

---

## Fallback Logic

Use the most specific reliable information available:

1. Local / city-level source
2. National source
3. Regional / continental source
4. Industry-average guidance

If local information is missing, do not stop. Move one level broader and label the result as national, regional, or industry-average guidance. Never present broad guidance as a confirmed local permission rule.

---

## Output

Regulatory Constraints is a single-output endpoint. Ignore Key takeaway, Explain the numbers, and Design implication distinctions for this skill.

Produce one concise regulatory brief:
- Overall stance: **Permissive**, **Moderate**, **Restrictive**, or **Unknown / needs local confirmation**
- Two to four facts that matter for early BIPV design
- Height/zoning risk if project height and a public height limit are both supplied
- Facade approval or aesthetic-review risk, especially for visible/street-facing BIPV
- Mandatory PV or solar-ready requirement if supplied by the sources
- Clear design consequence: what the architect should change, reserve, avoid, or document now
- Source website addresses
- A short precision note only when an exact local fact is missing, naming who to contact and what to ask

Keep the language formal, professional, and understandable to non-experts. Do not write methodology. Do not repeat the same caveat in several forms.

---

## Common Pitfalls

- Do not say the project is approved or non-compliant unless a supplied source explicitly supports that claim.
- Do not invent height limits, heritage status, setback rules, reflectivity limits, or permit timelines.
- Do not treat national or regional guidance as parcel-specific local approval.
- Do not give three separate mode-style answers. This skill should return one brief only.
- Do not end with only "conduct research"; the app has already done the broad research pass. If precision is missing, say exactly which local office to contact and exactly what to ask.
