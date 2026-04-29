---
name: site-potential--contextual-feasibility--regulatory-constraints
description: Use when the architect wants to understand what planning rules, permits, and design restrictions apply to BIPV in their project location. Uses the weather/location file inside the uploaded CEA output zip and lightweight public web research to retrieve current regulatory context for that city and country.
intent: Give the architect a clear picture of the regulatory environment before committing to a BIPV strategy — covering planning permits, height and zoning limits, heritage restrictions, facade material rules, and any mandatory BIPV requirements that apply to their building type and location.
type: component
position_in_tree: "Goal → Site Potential → Contextual Feasibility → Regulatory Constraints"
---

## Purpose

Answer the question: **"What local planning rules and permits apply to BIPV in this location?"**

This skill uses the project location extracted from the uploaded CEA output zip to search for current planning and regulatory requirements for BIPV installation. It covers both restrictions (what you cannot do) and mandates (what you may be required to do), giving the architect a complete regulatory picture before committing to a design strategy.

Important: regulatory information should come from supplied public/preloaded context, not from LLM guesswork. If a rule is not supplied, do not invent it.

This is a **pre-design** skill — regulatory constraints should be understood before design decisions are made, not discovered during planning approval.

---

## App Integration

This skill runs inside the BIPV Analyst web app, not inside CEA4.

The user uploads a zipped CEA output scenario. The app extracts the `.epw` weather file header from the zip, reads the city/country/latitude/longitude, and uses that location for lightweight public web research.

CEA mainly supplies the project location. When available, the app may also pass extracted project building heights from `zone_geometry.csv` so public height limits can be checked against the proposal. Planning/regulatory information itself comes from public source summaries supplied by the app.

---

## Data Sources

**Primary source: lightweight public web research supplied by the app**

The app performs targeted searches for the project location and supplies a compact source summary to the LLM. The search focus is:
- `"[city] BIPV planning permission requirements [current year]"`
- `"[country] solar panels building regulations facade [current year]"`
- `"[city] heritage conservation zone solar panels restrictions [current year]"`
- `"[city] building height limit zoning photovoltaic roof solar [current year]"`
- `"[city] zoning building height limit roof equipment photovoltaic [current year]"`
- `"[country] mandatory solar building code new construction [current year]"`
- `"[city] building permit photovoltaic facade roof [current year]"`

**Key information retrieved:**
- Whether planning permission is required for BIPV on facades and/or roofs
- Building height limits, zoning limits, and whether roof-mounted PV equipment counts toward height
- Any aesthetic or material restrictions (colour, reflectivity, flush-mounting requirements)
- Heritage or conservation zone restrictions
- Mandatory BIPV requirements for new construction (some cities require PV on new buildings above a certain size)
- Building type specific rules (residential vs commercial vs public buildings)

**Source quality:** Prioritise local planning authority websites, national building regulations, and official government sources. The LLM must use only supplied source summaries and should not invent current rules.

**Fallback logic:** Use the most specific available source. If city/canton/municipal information is missing, use national context. If national context is missing, use regional/continental context. If that is also missing, use industry-average BIPV planning guidance only as early design orientation. Always make the scale clear: local fact, national context, regional/continental fallback, or industry-average fallback. Do not present a national, regional, or industry-average rule as parcel-specific approval.

---

## Scale Behaviour

Regulatory constraints are a **location and building type** level analysis. Scale affects framing:

**District scale:**
- Highlights any district-level planning frameworks or masterplan requirements
- Flags if parts of the district fall within heritage or conservation zones
- Framing: "Across this district, the following regulatory contexts apply..."

**Cluster scale:**
- Identifies if individual buildings within the cluster have different regulatory status
- Framing: "Within this cluster, buildings facing [street] may be subject to additional facade restrictions..."

**Building scale:**
- Focuses on the specific building's regulatory context
- Framing: "For this building in [city], the following permits and restrictions apply..."

---

## Benchmark

**Regulatory environment indicators:**

| Indicator | Permissive | Moderate | Restrictive |
|-----------|-----------|----------|-------------|
| Planning permission | Not required | Simple notification | Full application required |
| Facade restrictions | None | Colour/reflectivity limits | Material match required |
| Heritage constraints | Not applicable | Adjacent to heritage area | Within conservation zone |
| Height / zoning limit | Clear margin below height limit | Close to limit or unclear roof-equipment rule | At/above limit or roof equipment counts against height |
| Mandatory requirements | None | Encouraged | Required by building code |

---

## Output Modes

The three output modes must complement each other:

- **Key takeaway** = decision and priorities: the regulatory stance and the one or two constraints that matter most for early design.
- **Explain the numbers** = evidence and terminology: what rules, thresholds, permit paths, dates, and source facts were found, and what each one means.
- **Design implication** = action recipe: how the architect should adapt surfaces, materials, visibility, documentation, and timeline.

Each mode must be understandable on its own, but it should not repeat the full content of the other two modes. If two modes would produce nearly the same answer, state the overlap clearly and shift the emphasis rather than repeating.

### If "Explain the numbers" selected:
**What the LLM produces:**
- Full overview of applicable planning requirements for the location
- Any mandatory BIPV requirements (some cities require solar on new construction)
- Height and zoning limits if supplied, including whether roof PV equipment may count toward the building height
- Heritage and conservation zone context if applicable
- Typical permit timeline and process
- Source and date for each piece of information
- Keep formal planning terminology where useful (e.g. permitted development, conservation area, heritage review, planning permission, building permit), but define it briefly in simple words.
- Do not repeat the Key takeaway wording. This mode is for the evidence behind the regulatory stance.
- Do not give the full design recipe; only state what each rule controls architecturally.

**Visualization:** Regulatory requirements checklist
- Itemised list of requirements with status: Required / Recommended / Not applicable
- Source links listed below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: overall regulatory environment rating for the location
- The two or three most important regulatory facts the architect needs to know
- Any critical restrictions that would significantly affect design
- If a supplied height limit is close to the extracted project height, flag it as a primary risk.
- Use formal, professional, non-expert language.
- Lead with the design consequence: what the architect should or should not assume before committing to BIPV.
- Include only the most important rule or threshold. Do not list every source, permit step, or document.

**Visualization:** Summary card
- Overall rating (Permissive / Moderate / Restrictive)
- Key facts as bullet points
- Designed to be shared with a client or design team

---

### If "Design implication" selected:
**What the LLM produces:**
- Concrete design recommendations based on regulatory context
- If heritage restrictions apply: recommend roof-only BIPV or flush-mounted facade systems that match existing materials
- If height limits apply: recommend low-profile roof BIPV, facade-integrated BIPV below the height envelope, or early authority consultation before relying on roof-mounted PV.
- If mandatory requirements exist: flag minimum BIPV coverage required and how that affects design
- If permit required: flag timeline and documentation needed
- Links to Infrastructure Readiness skill for grid connection context
- Focus on actions: surface choice, module appearance, reflectivity/colour, mounting depth, visibility from public realm, planning documentation, and submission timing.
- Treat height/zoning constraints as design drivers: they can cap roof PV, shift priority to facade-integrated PV, or require low-profile/flush-mounted systems.
- Use only the minimum regulatory values needed to justify each action.
- Do not re-explain every rule from Explain the numbers.

**Visualization:** Regulatory impact diagram
- Shows which surfaces are affected by which regulations
- Colour-coded by restriction level
- Designed to inform early design team discussion

---

## Common Pitfalls

- **Regulations change frequently:** Planning rules evolve — always display the date of retrieved information and encourage verification with local planning authorities before submission.
- **Local vs national rules:** Building regulations may exist at national, regional, and local levels simultaneously. The most restrictive level applies. Always search at all three levels and flag any conflicts.
- **Mandatory requirements are often missed:** Some cities (e.g. parts of California, France, certain Chinese cities) have mandatory solar requirements for new buildings. Architects sometimes discover these late — this skill is designed to surface them early.
- **Height constraints can be deal-breakers:** Roof-mounted PV or support structures may affect the legal building height in some jurisdictions. Only compare against a height limit when the limit is supplied by public/preloaded context; otherwise tell the architect exactly what to ask the planning authority.
- **Do not hallucinate legal values:** Never invent zoning names, maximum heights, roof-equipment exemptions, facade approval rules, or mandatory PV coverage.
- **This is not legal advice:** Always include a note that this information is for early feasibility orientation only and should be verified with a local planning consultant or authority before project submission.

---

## References

- CEA4 weather file location extraction
- Interview — Interviewee B: desired AI capability for "scenario suggestions based on context — climate, policy"
- IDP 2024 Team 8: noted Chinese government mandate for PV integration in newer commercial buildings in Shanghai
- IDP 2024 Team 2: regulatory context in Shanghai informed their BIPV strategy decisions
