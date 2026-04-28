---
name: site-potential--contextual-feasibility--infrastructure-readiness
description: "Use when the architect needs to understand whether BIPV fits the site's electricity and thermal infrastructure, and how grid/export constraints should shape design strategy."
intent: "Connect building-scale BIPV decisions to urban energy systems: grid export pressure, demand matching, transformer screening, supply-system compatibility, district heating/cooling context, and self-consumption strategy."
type: component
position_in_tree: "Goal -> Site Potential -> Contextual Feasibility -> Infrastructure Readiness"
---

## Purpose

Answer the question: **"Is the surrounding infrastructure ready for this BIPV strategy, and how should that affect the design?"**

This skill connects BIPV design decisions to infrastructure systems. It is **internet-required and CEA-supported**.

CEA can describe the project's pressure on infrastructure. It cannot, by itself, prove local grid readiness. Full readiness depends on local utility and policy data.

The skill should explain whether the design is likely to depend on:

- grid export capacity
- self-consumption
- load shifting or storage
- building electricity demand
- heating/cooling system type
- district heating or district cooling context
- grid carbon assumptions

This is an urban-systems translation node for architects.

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

External utility data required for a complete answer:

- live net metering or feed-in tariff status
- export limits and grid connection thresholds
- transformer / hosting capacity if published
- connection application process and timeline
- current local utility or government rules

If these facts are not supplied by a search/tool module, do not invent them. Give a provisional answer based on CEA project pressure only.

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

This class is only a **project-side pressure class** unless external utility data is also available.

Do not ask the LLM to infer these from raw CSV rows.

---

## LLM Role

Interpret the computed infrastructure summary for an architect.

The LLM should:

- start with infrastructure readiness: STRONG, MODERATE, CONSTRAINED, or UNKNOWN
- state whether the rating is complete or provisional
- explain whether the main issue is grid export, demand matching, or thermal-system compatibility
- say whether BIPV should be sized for self-consumption or maximum export
- explain whether BIPV electricity offsets the relevant building loads
- connect thermal-system type to the carbon narrative
- identify what information needs external verification

Important:

- If heating is boiler-based or district-heating-based, BIPV electricity does not directly offset heating carbon unless electric heating or heat pumps are in the system definition.
- If heat pumps, electric cooling, or electric domestic hot water are present, BIPV can be framed as supporting those electrical loads.
- If PV peak is high relative to demand or indicative transformer capacity, recommend self-consumption, load shifting, battery/thermal storage, or smaller/more distributed BIPV area before assuming export.
- Do not claim live utility approval status.
- Do not claim current tariff policy unless a search module provides a sourced result.
- If no internet/search result is present, say that CEA shows project-side pressure but not full local infrastructure readiness.

---

## Output Expectations

**Key takeaway**
- Start with the readiness rating and whether it is provisional.
- State the main infrastructure constraint or enabler.
- Give one design implication: self-consumption-first, export-ready, storage/load-shifting needed, or thermal-system mismatch.
- Do not lead with a raw PV/demand ratio. Translate it first into what the architect should do early in design.

**Explain the numbers**
- Explain peak PV, peak demand, annual PV/demand ratio, and transformer screening.
- Explain grid carbon/buy/sell assumptions if available.
- Explain supply-system compatibility: what BIPV electricity can and cannot offset.
- Say clearly which infrastructure facts are CEA-derived and which would need utility verification.

**Design implication**
- Give a practical design strategy.
- If export pressure is likely, orient the design around building loads rather than maximum generation.
- If thermal systems are not electric, do not oversell BIPV as solving heating carbon.
- If electric loads are present, suggest aligning PV surfaces/timing with those loads.
- Mention external utility checks only as next-step verification, not as already-known facts.
- Include early design allowances where relevant: inverter room, battery-ready area, risers, roof access, PV zoning, and future expansion route.

---

## Redundancy Rules

- Do not repeat generic policy caveats in every bullet.
- Do not describe charts.
- Do not say "grid readiness depends on local policy" unless you also state what the CEA data already shows.
- Do not turn this into an economics answer; keep the focus on infrastructure compatibility.

---

## Example Logic

If peak PV is high relative to demand:
- "Infrastructure Readiness: MODERATE. The BIPV system is feasible, but peak generation is large relative to building demand, so the design should prioritise self-consumed generation, load shifting, or staged PV area before assuming unrestricted export."

If heating is gas boiler or district heating:
- "BIPV electricity does not directly offset heating in the current system definition. Use BIPV for electric loads and be careful with the carbon narrative unless the design adds heat pumps or electric heating."

If district heating outputs are present:
- "The site appears connected to a thermal-network context. BIPV can reduce electrical demand, but heating decarbonisation depends on the district heating supply mix, not PV generation alone."
