---
name: site-potential--contextual-feasibility--infrastructure-readiness
description: "Use when the architect needs concept-phase guidance on how grid, electrical-room, storage-ready, and thermal-system constraints should shape a BIPV strategy."
intent: "Translate CEA energy-system evidence into early architectural decisions: PV ambition, self-consumption vs export, space reservations, cable/riser routes, storage readiness, thermal-system compatibility, and later utility checks."
type: component
position_in_tree: "Goal -> Site Potential -> Contextual Feasibility -> Infrastructure Readiness"
---

## Purpose

Answer the question: **"What should the architect allow for now so the BIPV strategy works with the local infrastructure context instead of becoming a late-stage technical problem?"**

This skill connects BIPV design decisions to infrastructure systems. It is **internet-first and CEA-supported**.

CEA can describe the project's pressure on infrastructure. Public/current information supplies the context: utility rules, export limits when published, tariff direction, grid-connection procedure, and who controls missing information. The LLM should do the annoying research translation and leave the architect with choices.

The skill should explain whether the design is likely to depend on:

- grid export capacity
- self-consumption
- load shifting or storage
- building electricity demand
- heating/cooling system type
- district heating or district cooling context
- grid carbon assumptions

This is an urban-systems translation node for architects. It should not feel like an electrical engineering report. It should feel like a concept-phase recipe: what we know, what it means, what design options exist, and what must be confirmed for precision.

---

## Data Used

Primary CEA data:

- `PV_PV*_total.csv`
- `PV_PV*_total_buildings.csv`
- `Total_demand_hourly.csv`
- individual building demand files, when building or cluster scale is selected
- `GRID.csv`
- `supply.csv`
- `SUPPLY_HEATING.csv`
- `SUPPLY_HOTWATER.csv`
- `SUPPLY_ELECTRICITY.csv`
- `SUPPLY_COOLING.csv`
- thermal-network output file presence, if available

External / internet context to look for:

- local distribution grid operator / utility for the project location
- live net metering, feed-in tariff, remuneration, or export compensation status
- export limits, grid connection thresholds, or inverter/export-control requirements
- transformer / hosting capacity if published
- connection application process and expected timeline
- metering, switchgear, protection, or application requirements relevant to PV
- current local utility, municipal, or government rules

If these facts are supplied by a search/tool module, interpret them for early design decisions. If exact values are not public, do not invent them. Keep the main answer useful using CEA project pressure and public context, then add a short precision note at the end saying who to contact and what to ask.

---

## What Python Should Calculate

Before calling the LLM, calculate a compact infrastructure summary:

- peak PV generation in kW
- annual PV generation in kWh/year
- peak electricity demand in kW
- annual electricity demand in kWh/year
- PV peak as a percentage of peak demand
- PV annual generation as a percentage of annual demand
- transformer screening using an explicitly labelled indicative transformer assumption if actual transformer data is missing
- grid carbon factor from `GRID.csv`
- grid buy/sell price assumptions from `GRID.csv`
- heating, hot water, cooling, and electricity supply-system descriptions
- whether district heating/cooling network outputs exist
- infrastructure readiness class:
  - STRONG: PV peak is small relative to demand and indicative transformer capacity
  - MODERATE: BIPV is feasible but export/self-consumption strategy matters
  - CONSTRAINED: peak generation could create export pressure without self-consumption, storage, or utility coordination
  - UNKNOWN: not enough data
- concept-phase stance:
  - MANAGEABLE: PV can be explored without immediately reducing area, while keeping future grid verification open
  - SELF-CONSUMPTION-FIRST: PV is plausible, but design should prioritise load matching, storage-ready space, or staged PV
  - EXPORT-SENSITIVE: the concept should not assume all high-irradiation surfaces can export freely
  - UNKNOWN: keep PV/electrical routes flexible until missing data is available
- early design allowances:
  - inverter/electrical room
  - battery-ready or storage-ready area where relevant
  - vertical risers and short cable routes
  - switchgear/metering/export connection allowance
  - roof/facade access for maintenance
  - staged PV zones or future expansion paths
- specific PV staging proposal:
  - explanation that staging means not every facade PV panel must be installed and connected on day one
  - explanation that BIPV should be divided into phases or zones so active PV area can respond to export capacity, budget, and utility approval while the facade remains coherent
  - Stage 1 / must-keep PV zone from simulated surface generation and area
  - Stage 2 / expansion PV zones from the next-best surfaces
  - Stage 3 / optional PV-ready or visually compatible non-PV cladding zones
- concept-stage equipment-space allowance:
  - approximate inverter/electrical room area based on PV peak
  - approximate battery/load-shifting-ready area based on export-pressure class
  - preferred location relative to dominant PV surfaces, main riser, and grid/metering room
- architectural control variables for the numbers:
  - PV peak vs demand peak -> whether to keep maximum PV area, prioritise self-consumption, or stage PV zones
  - annual PV vs annual demand -> whether the BIPV story is partial load support, near-annual matching, or export-sensitive
  - transformer screening -> whether to reserve more space for switchgear/metering/export connection
  - cable-route constraint -> where inverter/electrical rooms and risers should be placed once the project-specific maximum route length is known

This class is only a **project-side pressure class** unless external utility data is also available.

Do not ask the LLM to infer these from raw CSV rows.

---

## LLM Role

Interpret the computed infrastructure summary for an architect.

The LLM should:

- start with the concept-phase stance, not with a raw ratio
- state whether the rating is complete or provisional
- explain what the architect should preserve, resize, stage, or leave flexible
- say whether the BIPV concept should prioritise self-consumption, staged PV area, or export-ready design
- explain whether BIPV electricity offsets the relevant building loads
- connect thermal-system type to the carbon narrative
- interpret public utility/policy facts when supplied
- identify missing precision items only after giving useful design guidance

Important:

- If heating is boiler-based or district-heating-based, BIPV electricity does not directly offset heating carbon unless electric heating or heat pumps are in the system definition.
- If heat pumps, electric cooling, or electric domestic hot water are present, BIPV can be framed as supporting those electrical loads.
- If PV peak is high relative to demand or indicative transformer capacity, recommend self-consumption, load shifting, battery/thermal storage, or smaller/more distributed BIPV area before assuming export.
- Do not claim live utility approval status.
- Do not claim current tariff policy unless a search module provides a sourced result.
- If no internet/search result is present, stay with CEA-derived design guidance and add only a short precision note if it would help the architect get a better answer.
- Do not write "the most important finding is the PV peak / demand peak ratio." Use the ratio only as evidence for a design stance.
- Do not tell the architect to "invest in energy storage" as a generic answer. Say what the concept should reserve or keep possible: battery-ready room, plant-room allowance, riser capacity, load-shifting program, or staged PV zones.
- Do not invent maximum cable lengths, inverter distances, transformer limits, or room sizes if they are not in the data. If cable length matters, phrase it as an architectural control: locate electrical rooms/risers within the project-specific allowed route distance once the electrical design limit is known.
- If the computed metrics provide a stage-by-stage PV proposal or concept equipment-space allowance, use those specific surfaces and square metres. Do not replace them with generic "make it stageable" language.
- Before listing Stage 1 / Stage 2 / Stage 3, explain the reasoning: the architect should not design the facade so every PV panel must be installed and connected on day one; instead, divide facade/roof BIPV into phases or zones.
- Only list Stage 1 / Stage 2 / Stage 3 when the computed metrics say staged PV is recommended. If the metrics say staged facade PV is not required, say that clearly and do not invent a staging recipe.
- Clearly label equipment-room and battery-ready areas as concept allowances, not final engineering dimensions.
- Exact public grid information, when supplied, should be translated into concept decisions: how much PV area to stage, whether facade PV should be self-consumption-first, whether to reserve more switchgear/metering space, and whether storage-ready space is worth protecting.
- Missing exact grid information should be handled as an action item, not as a failure: "For a more precise result, ask the local distribution grid operator for the point-of-connection export limit, nearest transformer spare capacity, PV connection threshold, metering/protection requirements, and application timeline."

---

## Output Expectations

**Key takeaway**
- Start with the concept-phase infrastructure stance and whether it is provisional.
- State the design consequence in plain architectural language.
- Use formal, professional language that a non-expert architect can understand. Avoid unnecessary technical terminology.
- Give clear priorities for the architect:
  - first: which PV surfaces should be Stage 1 and Stage 2
  - second: the approximate service/equipment space to reserve in square metres
  - third: what must stay flexible until utility/electrical data is confirmed
- If mentioning stages, first define what staging means in one sentence.
- If staging is not recommended by the computed metrics, replace the staging priority with the highest-value active PV surface and basic spare riser capacity.
- Do not lead with a raw PV/demand ratio. Translate it first into what the architect should do early in design.
- Keep this mode short and decision-oriented.
- Mention exact transformer capacity, export cap, tariff, or utility rule only if it is actually supplied. If not supplied, focus the main answer on priorities and add a one-line precision note only if useful.

**Explain the numbers**
- Keep the main numbers visible: peak PV, peak demand, annual PV generation, annual electricity demand, PV peak/demand percentage, annual PV/demand percentage, and transformer screening.
- Keep the correct technical terminology, but define it in simple language the first time it appears.
- After each important number, state what it controls architecturally.
- Example: "PV peak is 128.5 kW against a 249.1 kW demand peak, or 51.6%. This does not mean the building exports all solar power; it means the concept should still keep self-consumption and low-load sunny hours in mind."
- Explain the specific Stage 1 / Stage 2 / Stage 3 PV surfaces with their generation, area, and yield if supplied.
- Before the stage list, explain why staged BIPV is useful for concept design.
- If the computed metrics say staging is not required, explain why the project can connect the strongest PV surfaces directly instead of listing stages.
- Explain the concept equipment-space allowance in square metres and where it should sit in the building.
- Explain grid carbon/buy/sell assumptions if available.
- Explain supply-system compatibility: what BIPV electricity can and cannot offset.
- If sourced public grid information is supplied, explain how it changes the interpretation of the CEA numbers. If an exact value is missing, place that in a short "to make this precise" note after the answer, with the responsible contact and exact question.
- If mentioning cable routes, explain them through design control: room/riser placement within an allowed route distance, not vague "short cable length."

**Design implication**
- Give a practical concept strategy.
- If export pressure is likely, orient the design around building loads rather than maximum generation.
- If thermal systems are not electric, do not oversell BIPV as solving heating carbon.
- If electric loads are present, suggest aligning PV surfaces/timing with those loads.
- Mention external utility facts when supplied by search/data. If exact utility values are missing, end with a concise action note naming the missing value, the likely responsible party, and the design decision it would refine.
- Include early design allowances where relevant: inverter room, battery-ready area, risers, roof access, PV zoning, and future expansion route.
- Give the actual staging recipe from the computed metrics: what gets connected first, what is PV-ready for later, and what can become normal cladding if grid/export constraints are tight.
- Before giving the staging recipe, explain that staging keeps the facade design coherent while avoiding a one-shot commitment to every PV panel being active from day one.
- If the computed metrics say staging is not required, do not use Stage 1 / Stage 2 / Stage 3. Give the active PV priority and service-space placement instead.
- Give the approximate service-room and storage-ready square metres from the computed metrics, and say where to place them relative to the dominant PV surface and grid/metering point.
- Where useful, write the answer as "Reserve / Avoid / Keep flexible / Verify later" so it is easy to act on during concept design.
- When giving measurable advice, use only project-derived numbers or explicitly label missing values as "to be confirmed." Do not make up cable distances, transformer capacity, room area, or storage size.

---

## Redundancy Rules

- Do not repeat generic policy caveats in every bullet.
- Do not describe charts.
- Do not say "grid readiness depends on local policy" unless you also state what the CEA data already shows.
- Do not turn this into an economics answer; keep the focus on infrastructure compatibility.
- Do not repeat annual PV generation in multiple bullets unless each use adds a new design consequence.
- Do not present a large generation number as automatically good; connect it to self-consumption, export risk, storage readiness, or staging.
- Do not bury the architect in uncertainty. Put research/benchmark findings into the main recommendation; put missing precision items at the end.
- Do not use the word "stageable" without saying what the stages are.

---

## Example Logic

If peak PV is high relative to demand:
- "Concept-phase stance: SELF-CONSUMPTION-FIRST. Keep the high-value PV surfaces, but do not design the scheme as export-only; reserve inverter/riser capacity and a battery-ready or load-shifting option."

If peak PV is modest relative to demand:
- "Concept-phase stance: MANAGEABLE. The current PV ambition is not the main infrastructure risk, so the concept can prioritise the best architectural PV surfaces while keeping spare riser capacity for later expansion."

If heating is gas boiler or district heating:
- "BIPV electricity does not directly offset heating in the current system definition. Use BIPV for electric loads and be careful with the carbon narrative unless the design adds heat pumps or electric heating."

If district heating outputs are present:
- "The site appears connected to a thermal-network context. BIPV can reduce electrical demand, but heating decarbonisation depends on the district heating supply mix, not PV generation alone."
