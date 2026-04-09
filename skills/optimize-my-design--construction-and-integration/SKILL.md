---
name: optimize-my-design--construction-and-integration
description: Use when the architect wants practical guidance on how to integrate BIPV into their building design — covering structural requirements, waterproofing, electrical routing, maintenance access, and panel mounting systems for roof and facade applications.
intent: Surface the practical integration details that architects often overlook during early design — and that become expensive to resolve later — so that BIPV integration is considered as part of the architectural design process, not as an afterthought during construction documentation.
type: component
position_in_tree: "Goal → Optimize My Design → Construction & Integration"
---

## Purpose

Answer the question: **"What do I need to know about integrating BIPV into my building from a construction and systems perspective?"**

This skill provides practical integration guidance based on the architect's specific project context — the surfaces selected for BIPV, the building type, and the location. It covers the details that are not in any CEA output but that directly affect whether BIPV gets built as designed and performs as expected.

It covers:
- **Structural requirements** — additional loads, fixing systems, structural zones to avoid
- **Waterproofing** — roof integration, facade drainage, junction details
- **Electrical integration** — inverter placement, cable routing, connection to building systems
- **Maintenance access** — clearance zones, cleaning requirements, inspection access
- **Roof vs facade specific guidance** — fundamentally different integration approaches
- **Panel tilt and self-shading** — how tilt angle affects row spacing and effective roof coverage

---

## CEA4 Integration

This skill runs as a CEA4 plugin.

**Location context** read automatically from project weather file:
```python
locator.get_weather()  # → city, latitude, longitude, climate zone
```

**PV simulation settings** read from CEA config:
```python
# panel-tilt-angle: used tilt angle (degrees)
# custom-tilt-angle: whether architect defined tilt or CEA optimised it
# panel-on-roof / panel-on-wall: which surfaces were simulated
# type-pvpanel: which panel types were selected
```

**Installed area and surface data** accessed via InputLocator:
```python
locator.get_pv_results(panel_type="PV1")
# → PV_PV{n}_total_buildings.csv
# area_PV_m2 per surface — tells us scale of installation
```

**Internet search** for current best practice:
- Structural load requirements for roof PV and facade BIPV in the project location
- Waterproofing and junction details for the climate zone
- Electrical regulation requirements for grid connection in the project country
- Maintenance access standards and clearance requirements
- Current BIPV cladding system options and their integration requirements

---

## Data Sources

**From CEA (via InputLocator):**
- Panel tilt angle from simulation settings
- Which surfaces have PV installed (roof / wall)
- Installed area per surface
- Panel type selected

**From Internet search (location and building-type specific):**
- Local structural load standards for PV systems
- Electrical connection and inverter requirements
- Waterproofing standards for the climate zone
- Maintenance access regulations
- Available BIPV cladding systems and their specifications

---

## Key Integration Topics

### Roof PV Integration
- **Mounting system:** ballasted (no penetrations) vs mechanically fixed (penetrations require waterproofing)
- **Tilt angle and row spacing:** steeper tilt → more yield per panel but more spacing needed → less panels per m² of roof
- **Self-shading calculation:** minimum row spacing to avoid front row shading rear row at winter solstice
- **Structural zones:** avoid skylights, HVAC units, access hatches — typically 15% of roof area
- **Drainage:** panels must not impede roof drainage — gutters and downpipes must be accessible
- **Access:** 600mm minimum clearance around panels for maintenance

### Facade BIPV Integration
- **System type:** ventilated rainscreen BIPV vs curtain wall integrated BIPV — very different structural and waterproofing approach
- **Panel as cladding:** replaces conventional facade material — cost offset partially compensates for BIPV premium
- **Structural fixing:** panels fixed to substructure — must accommodate thermal movement
- **Waterproofing:** open-joint vs closed-joint systems — drainage path must be designed
- **Electrical routing:** cables run within facade cavity — must be accessible for maintenance
- **Junction details:** roof-to-facade, window-to-panel, corner conditions all need specific detailing

### Electrical Integration
- **Inverter placement:** string inverters (1 per array) vs microinverters (1 per panel) — affects performance and maintenance
- **Cable routing:** DC cables from panels to inverter, AC cables to distribution board
- **Grid connection:** metering, protection relay, utility approval — varies by country
- **Building management system:** integration with BMS for monitoring and optimisation

---

## Scale Behaviour

**District scale:**
- Overview of integration considerations for the district
- Flags any district-level electrical infrastructure requirements (shared inverter rooms, district metering)

**Cluster scale:**
- Integration considerations for the cluster as a whole
- Identifies shared infrastructure opportunities (shared inverter room, common cable routes)

**Building scale:**
- Most useful — specific integration guidance for a single building
- Tailored to the building's surfaces, panel type, and local requirements

---

## Output Modes

### If "Explain the numbers" selected:
**What the LLM produces:**
- Tilt angle used in simulation and what it means for row spacing
- Estimated structural load per m² of installation and structural zone requirements
- Electrical system overview: inverter type, estimated number, placement requirements
- Waterproofing approach for roof and facade surfaces
- Maintenance access requirements and clearance zones

**Visualization:** Integration requirements checklist
- Itemised by category: Structural / Waterproofing / Electrical / Maintenance
- Status: Considered in design / Needs attention / Not applicable
- Source for each requirement

---

### If "Key takeaway" selected:
**What the LLM produces:**
- The three most important integration considerations for this specific project
- Any critical details that are often missed for this building type and surface combination
- One sentence on the biggest difference between roof and facade integration if both are present

**Visualization:** Integration priority card
- Three key considerations with brief explanation each
- Designed for design team briefing

---

### If "Design implication" selected:
**What the LLM produces:**
- Specific design decisions that need to be made now (early design) vs later (detailed design)
- **Decide now:** tilt angle, surface selection, inverter room location, facade system type
- **Decide later:** specific panel layout, cable routes, junction details
- Recommendation on roof vs facade integration sequence — roof first (simpler) then facade
- Note on BIPV as cladding replacement — cost offset calculation
- Links to Surface Prioritization skill — integration complexity should inform surface priority
- Links to Envelope Simplification skill — simpler geometry reduces integration complexity

**Visualization:** Integration decision timeline
- Design stages along X axis (concept / schematic / developed / technical)
- Integration decisions mapped to each stage
- Highlights what needs to be locked in at concept stage

---

## Common Pitfalls

- **Tilt angle trade-off:** CEA optimises tilt for maximum yield per panel — but this increases row spacing and reduces total panels per m² of roof. Always explain this trade-off clearly.
- **Facade BIPV cost:** Facade BIPV typically costs 2–4× more per m² than roof PV. However, it replaces cladding — so the net premium is lower. Always calculate net cost, not gross cost.
- **Electrical regulations vary by country:** Grid connection requirements, protection relay specifications, and metering arrangements differ significantly between countries. Always verify with a local electrical engineer.
- **Maintenance is often forgotten:** BIPV panels need cleaning 1–2 times per year. Access provisions must be designed in — especially for high facades. Retrofitting access is extremely expensive.
- **This is guidance, not engineering:** Always note that structural, waterproofing, and electrical integration must be confirmed by qualified engineers for the specific project.

---

## References

- CEA4 PV simulation settings documentation
- IDP 2024 Team 8: noted practical constraints of BIPV installation on specific building archetypes
- IDP 2025 Team 3: facade BIPV integration as part of urban design strategy
- Poll result: architects want "design implications" — practical guidance on what to do, not just what the numbers mean
- Interview — Interviewee A: wished for clearer guidance on what CEA results mean for actual design decisions
