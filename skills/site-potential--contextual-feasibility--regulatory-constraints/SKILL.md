---
name: site-potential--contextual-feasibility--regulatory-constraints
description: Use when the architect wants to understand what planning rules, permits, and design restrictions apply to BIPV in their project location. Uses location from CEA weather file and internet search to retrieve current regulatory context for that city and country.
intent: Give the architect a clear picture of the regulatory environment before committing to a BIPV strategy — covering planning permits, heritage restrictions, facade material rules, and any mandatory BIPV requirements that apply to their building type and location.
type: component
position_in_tree: "Goal → Site Potential → Contextual Feasibility → Regulatory Constraints"
---

## Purpose

Answer the question: **"What local planning rules and permits apply to BIPV in this location?"**

This skill uses the project location (read automatically from the CEA weather file) to search for current planning and regulatory requirements for BIPV installation. It covers both restrictions (what you cannot do) and mandates (what you may be required to do), giving the architect a complete regulatory picture before committing to a design strategy.

This is a **pre-design** skill — regulatory constraints should be understood before design decisions are made, not discovered during planning approval.

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
- `"[city] BIPV planning permission requirements [current year]"`
- `"[country] solar panels building regulations facade [current year]"`
- `"[city] heritage conservation zone solar panels restrictions [current year]"`
- `"[country] mandatory solar building code new construction [current year]"`
- `"[city] building permit photovoltaic facade roof [current year]"`

**Key information retrieved:**
- Whether planning permission is required for BIPV on facades and/or roofs
- Any aesthetic or material restrictions (colour, reflectivity, flush-mounting requirements)
- Heritage or conservation zone restrictions
- Mandatory BIPV requirements for new construction (some cities require PV on new buildings above a certain size)
- Building type specific rules (residential vs commercial vs public buildings)

**Source quality:** The LLM prioritises local planning authority websites, national building regulations, and official government sources. It flags when information may be outdated and provides the source and date of each piece of information.

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
| Mandatory requirements | None | Encouraged | Required by building code |

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Full overview of applicable planning requirements for the location
- Any mandatory BIPV requirements (some cities require solar on new construction)
- Heritage and conservation zone context if applicable
- Typical permit timeline and process
- Source and date for each piece of information

**Visualization:** Regulatory requirements checklist
- Itemised list of requirements with status: Required / Recommended / Not applicable
- Source links listed below

---

### If "Key takeaway" selected:
**What the LLM produces:**
- One headline: overall regulatory environment rating for the location
- The two or three most important regulatory facts the architect needs to know
- Any critical restrictions that would significantly affect design

**Visualization:** Summary card
- Overall rating (Permissive / Moderate / Restrictive)
- Key facts as bullet points
- Designed to be shared with a client or design team

---

### If "Design implication" selected:
**What the LLM produces:**
- Concrete design recommendations based on regulatory context
- If heritage restrictions apply: recommend roof-only BIPV or flush-mounted facade systems that match existing materials
- If mandatory requirements exist: flag minimum BIPV coverage required and how that affects design
- If permit required: flag timeline and documentation needed
- Links to Infrastructure Readiness skill for grid connection context

**Visualization:** Regulatory impact diagram
- Shows which surfaces are affected by which regulations
- Colour-coded by restriction level
- Designed to inform early design team discussion

---

## Common Pitfalls

- **Regulations change frequently:** Planning rules evolve — always display the date of retrieved information and encourage verification with local planning authorities before submission.
- **Local vs national rules:** Building regulations may exist at national, regional, and local levels simultaneously. The most restrictive level applies. Always search at all three levels and flag any conflicts.
- **Mandatory requirements are often missed:** Some cities (e.g. parts of California, France, certain Chinese cities) have mandatory solar requirements for new buildings. Architects sometimes discover these late — this skill is designed to surface them early.
- **This is not legal advice:** Always include a note that this information is for early feasibility orientation only and should be verified with a local planning consultant or authority before project submission.

---

## References

- CEA4 weather file location extraction
- Interview — Interviewee B: desired AI capability for "scenario suggestions based on context — climate, policy"
- IDP 2024 Team 8: noted Chinese government mandate for PV integration in newer commercial buildings in Shanghai
- IDP 2024 Team 2: regulatory context in Shanghai informed their BIPV strategy decisions
