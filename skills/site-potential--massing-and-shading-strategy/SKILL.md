---
name: site-potential--massing-and-shading-strategy
description: "Use when the architect wants to understand how site massing, surrounding buildings, and shading affect solar access, and what form changes would maximise BIPV potential."
intent: "Turn irradiation and surrounding-geometry evidence into massing recommendations: where to keep height, where to step down, where to increase setbacks, which surfaces to prioritise, and when the building form itself should change."
type: component
position_in_tree: "Goal -> Site Potential -> Massing & Shading Strategy"
---

## Purpose

Answer the question: **"What massing strategy would give this project the best solar access for BIPV?"**

This skill is not a surface-ranking skill. It is a form-making and shading strategy node. It should integrate:

- surrounding building geometry and height
- project building geometry and height
- project-to-project shading / mutual obstruction between buildings in the scheme
- annual irradiation by building and opaque surface
- likely obstruction directions
- best solar-exposed surfaces
- surfaces that are weak enough to deprioritise
- massing changes that could improve the result

The form is allowed to change substantially if that is the best solar strategy. Do not assume the existing massing is fixed unless the user says it is.

---

## Data Used

Primary:
- `zone.shp` / `zone.dbf`, extracted as compact project geometry
- `surroundings.shp` / `surroundings.dbf`, extracted as compact surrounding geometry
- `solar_irradiation_annually_buildings.csv`

Useful fields:
- building name
- height or floors above ground
- footprint bounding box and centroid
- annual roof irradiation
- annual north/south/east/west wall irradiation

Important:
- CEA irradiation values already include shading from the surroundings file. Do not apply another numerical shading penalty.
- Use geometry to explain likely causes and design responses.

---

## What Python Should Calculate

Before calling the LLM, calculate a compact massing/shading summary:

- total opaque-surface irradiation per building
- best and weakest surface per building
- best facade per building
- selected building height, footprint, and nearby surrounding heights
- nearest/tall surrounding buildings
- nearest/tall project buildings that may shade other project buildings
- at building scale, compare the selected building against all other project buildings, not only external surroundings
- likely obstruction direction: north, south, east, west
- whether a neighbour is within an approximate 2H influence distance
- massing options that match the evidence

Do not ask the LLM to infer these values from raw shapefile or CSV rows.

---

## LLM Role

Use the computed metrics to propose a massing strategy.

The LLM should:

- name the massing strategy first
- identify the dominant shading/context issue
- distinguish external obstructions from project-to-project mutual shading
- at building scale, explicitly state whether the selected building is constrained by other project buildings
- say which building/surface should carry most BIPV
- say which surfaces should be deprioritised
- propose form changes when they improve solar access
- distinguish current-condition advice from redesign advice

Possible massing moves:

- step the building down toward the south
- increase setback from tall south/east/west neighbours
- shift height or dense program volume northward
- elongate the mass east-west to create a stronger south-facing BIPV plane
- split one bulky volume into thinner bars to reduce self-shading
- lower or terrace upper floors where they shade useful roof/facade areas
- keep service cores or low-PV program on weakly irradiated sides
- reserve the strongest roof plane as the baseline solar collector
- rotate or reorient the mass if the current orientation suppresses the best facade
- subtractive massing: remove parts of a larger starting volume to improve solar exposure
- courtyard massing: carve an internal void when it increases useful facade/daylight access
- atrium massing: use a larger internal void when solar/daylight and program organisation benefit
- stilted or lifted massing: lift part of the volume to improve porosity, daylight, or shadow relationships
- solar-envelope massing: shape the volume around solar access constraints
- split-bar massing: divide a bulky block into thinner bars to reduce self-shading

Do not give generic urban-design advice. Every recommendation must connect to a specific computed obstruction, surface, or irradiation result.

---

## Output Expectations

**Key takeaway**
- Start with the optimal massing move.
- Name the surface/building that should carry the main BIPV area.
- Mention the biggest shading constraint or obstruction direction.
- End with one direct design action.

**Explain the numbers**
- Explain the solar-access ranking.
- For the selected building or cluster, explain best surface, weakest surface, and nearby obstruction context.
- Explain how the geometry supports the shading interpretation.
- Do not repeat that "CEA includes shading" unless it prevents a misunderstanding.

**Design implication**
- Give a design recipe.
- Include current-condition placement advice and redesign advice.
- If the most solar-optimal solution requires changing the form, say so directly.
- When substantial redesign is useful, name the relevant massing option so the architect can look it up, for example subtractive massing, courtyard massing, stilted massing, solar-envelope massing, split-bar massing, or terraced massing.
- Deprioritise surfaces that are weak or likely shaded.
- Use massing language: step, setback, shift, split, elongate, rotate, terrace, reserve.

---

## Redundancy Rules

- Do not restate surface irradiation rankings from Surface Irradiation unless they drive a massing decision.
- Do not list every surrounding building unless it changes the design recommendation.
- Do not describe charts.
- Do not promise exact recovered kWh from a massing move unless a rerun simulation exists.
- Do not invent trees, terraces, heritage constraints, or client goals.

---

## Example Logic

If a tall neighbour is close to the south:
- "Step the mass down toward the south and keep the highest volume north. The south-side obstruction is within the 2H influence zone, so a taller southern edge would compound shading instead of creating useful BIPV area."

If one project building shades another:
- "Treat this as a massing coordination issue, not only a PV placement issue. Increase spacing, step the taller block, shift height northward, or split the volume so the lower building keeps useful roof and south-facade exposure."

If the roof dominates irradiation:
- "Keep the roof plane large and unbroken. This is the primary BIPV collector; avoid fragmenting it with terraces, plant zones, or irregular roof volumes unless those constraints are intentional."

If an east or west neighbour is close:
- "Do not rely on that facade for morning/afternoon generation. Shift BIPV effort to the roof and the less obstructed facade, or increase the side setback before treating the facade as a main PV surface."

If one compact block performs poorly:
- "Consider splitting the mass into thinner bars or stepping upper floors. The goal is not just to place panels differently, but to create more unshaded roof and facade exposure."

If the current mass is too bulky for solar access:
- "Use subtractive massing as the redesign strategy: start from the allowed volume and remove/carve portions that block useful roof or facade exposure. Test courtyard, split-bar, or terraced variants before finalising the BIPV area."
