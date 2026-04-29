---
name: "optimize-my-design--pv-coverage-scenario"
description: "Use when the architect wants to test how different active PV coverage percentages affect cost, carbon, self-sufficiency, and visual coverage."
intent: "Provide a local interactive PV coverage slider from 0% to 100% of the recommended active PV module area. Store the selected scenario so the Design Integration Recipe can use it."
type: "local-tool"
position_in_tree: "Goal -> Optimize My Design -> PV Coverage Scenario"
---

## Purpose

This is a local scenario tool, not an LLM prompt. It helps architects see what happens when they choose to activate only part of the recommended PV area.

The tool should:
- Show a 0-100% slider.
- Render a simple building/facade visual so the coverage percentage is visible.
- Recalculate active PV area, annual PV generation, estimated investment, self-sufficiency, export, and avoided carbon locally.
- Save the selected scenario so the Design Integration Recipe can use it.

## Rule

The percentage scales the CEA simulated active PV module area. It does not mean the whole physical roof or whole physical facade is coverable.
