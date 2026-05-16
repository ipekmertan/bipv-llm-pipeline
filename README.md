---
title: BIPV Analyst
emoji: ☀️
colorFrom: yellow
colorTo: pink
sdk: streamlit
sdk_version: 1.35.0
app_file: app.py
pinned: false
---
# BIPV Analyst

A web-based prototype that helps architects interpret Building-Integrated Photovoltaics (BIPV) simulation results from the City Energy Analyst (CEA4). Upload your CEA project folder, select what you want to understand, and get plain-language analysis with design-ready insights.

Built as part of the ETH Zürich semester project **From Simulation to Interpretation: Bridging BIPV Energy Modelling and Design Reasoning through LLM-Assisted Workflow**.

---

## What it does

CEA4 produces detailed BIPV simulation outputs — irradiation CSVs, energy yield files, carbon and cost data — but presenting and interpreting these results requires significant manual effort. This tool explores a post-simulation processing workflow that makes those outputs easier to interpret during early architectural design.

The architect uploads their CEA project zip, chooses what they want to understand (e.g. which surfaces are worth covering, what the carbon payback period is, how panel types compare), and receives a focused, design-relevant answer based on their actual simulation data. The LLM is used as an assistive interpretation layer: structured Python processing extracts project evidence, and predefined analysis skills shape that evidence into design-facing explanations.

---

## Research framing

This repository supports a semester project at the Chair of Architecture and Building Systems, ETH Zürich. The project investigates whether an LLM-assisted post-processing layer can improve the interpretability of CEA BIPV outputs for architects and encourage earlier engagement with performance data while form, orientation, facade systems, and integration strategies are still flexible.

The prototype is informed by:

- review of CEA documentation, BIPV post-processing practices, and LLM-assisted numerical interpretation workflows
- user workflow analysis with students who previously used CEA for BIPV-related design work
- designer-needs research around how architects prefer to receive simulation evidence during conceptual design
- experimental validation comparing standard CEA outputs with the LLM-enhanced workflow for a BIPV integration task

The intended output is a documented semester-project prototype with a final report, codebase, example dataset, processed outputs, and a walkthrough demonstration.

---

## How to use it

1. Run your BIPV simulations in CEA4
2. Compress your CEA project folder to a `.zip` file
3. Upload it at [bipv-analyst.hf.space](https://huggingface.co/spaces/ipekmertan/bipv-analyst)
4. Select an analysis from the decision tree
5. Choose your output mode: **Key takeaway**, **Explain the numbers**, or **Design implication**
6. Ask follow-up questions in the chat

The workflow is designed around the research proposal's goal: bridging technical CEA outputs and architectural design reasoning. It does not replace CEA4 simulation; it helps translate existing simulation results into interpretable, design-relevant evidence.

---

## Repository structure

```
bipv-llm-pipeline/
│
├── app.py                        ← Streamlit web application (main entry point)
├── requirements.txt              ← Python dependencies
│
├── skills/                       ← Skill prompt files and supporting analysis modules
│
└── configuration/
    └── skills-index.json         ← Decision tree structure, tooltips, skill metadata
```

The app's live decision tree is configured in `configuration/skills-index.json`. Most entries map to a `SKILL.md` file; a few interactive/local-calculation endpoints are handled directly in `app.py`.

---

## Decision tree

```
Site Potential
 ├── Solar Availability
 │    ├── Surface Irradiation
 │    └── Temporal Availability
 │         ├── Seasonal Patterns
 │         ├── Daily Patterns
 │         └── Storage Necessity
 ├── Envelope Suitability
 ├── Massing & Shading Strategy
 └── Contextual Feasibility
      ├── Infrastructure Readiness
      ├── Regulatory Constraints
      └── Basic Economic Signal

Performance Estimation
 ├── Energy Generation
 ├── Self Sufficiency
 └── Panel Type Trade-off

Impact and Viability
 ├── Carbon Impact
 │    ├── Carbon Footprint
 │    └── Carbon Payback Period
 └── Cost Analysis

Optimize My Design
 ├── PV Coverage Scenario
 └── Design Integration Recipe
```

---

## Running locally

```bash
git clone https://github.com/ipekmertan/bipv-llm-pipeline.git
cd bipv-llm-pipeline
pip install -r requirements.txt

# Add your Groq API key
mkdir -p .streamlit
printf 'GROQ_API_KEY = "your-groq-api-key"\n' > .streamlit/secrets.toml

streamlit run app.py
```

---

## Tech stack

- **Frontend & backend:** [Streamlit](https://streamlit.io)
- **LLM:** Groq API via `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`
- **Data processing:** pandas
- **Hosting:** Hugging Face Spaces
- **Simulation data source:** [City Energy Analyst (CEA4)](https://github.com/architecture-building-systems/CityEnergyAnalyst)

---

## Context

This tool is developed as part of a semester project at ETH Zürich. The project asks whether an LLM layer can improve the interpretability of energy simulation data for architects, increase clarity and confidence, and support more sustainable decisions in early design stages.
