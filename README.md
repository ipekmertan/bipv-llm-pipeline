---
title: BIPV Analyst
emoji: ☀️
colorFrom: yellow
colorTo: orange
sdk: docker
app_file: app.py
pinned: false
---
# BIPV Analyst

A web-based tool that helps architects interpret Building-Integrated Photovoltaics (BIPV) simulation results from the City Energy Analyst (CEA4). Upload your CEA project folder, select what you want to understand, and get plain-language analysis with design-ready insights.

Built as part of an MAS thesis at ETH Zürich, 2026.

---

## What it does

CEA4 produces detailed BIPV simulation outputs — irradiation CSVs, energy yield files, carbon and cost data — but presenting and interpreting these results requires significant manual effort. This tool automates that interpretation step using an LLM pipeline structured around a decision tree of 18 analysis skills.

The architect uploads their CEA project zip, chooses what they want to understand (e.g. which surfaces are worth covering, what the carbon payback period is, how panel types compare), and receives a focused, design-relevant answer based on their actual simulation data.

---

## How to use it

1. Run your BIPV simulations in CEA4
2. Compress your CEA project folder to a `.zip` file
3. Upload it at [bipv-analyst.hf.space](https://huggingface.co/spaces/ipekmertan/bipv-analyst) *(link to be added after deployment)*
4. Select an analysis from the decision tree
5. Choose your output mode: **Key takeaway**, **Explain the numbers**, or **Design implication**
6. Ask follow-up questions in the chat

---

## Repository structure

```
bipv-llm-pipeline/
│
├── app.py                        ← Streamlit web application (main entry point)
├── requirements.txt              ← Python dependencies
│
├── skills/                       ← 18 analysis modules, one per SKILL.md
│   ├── site-potential--solar-availability--surface-irradiation/
│   ├── site-potential--solar-availability--temporal-availability--seasonal-patterns/
│   ├── site-potential--solar-availability--temporal-availability--daily-patterns/
│   ├── site-potential--envelope-suitability/
│   ├── site-potential--massing-and-shading-strategy/
│   ├── site-potential--contextual-feasibility--infrastructure-readiness/
│   ├── site-potential--contextual-feasibility--regulatory-constraints/
│   ├── site-potential--contextual-feasibility--basic-economic-signal/
│   ├── performance-estimation--energy-generation/
│   ├── performance-estimation--self-sufficiency/
│   ├── impact-and-viability--carbon-impact--operational-carbon-footprint/
│   ├── impact-and-viability--carbon-impact--carbon-payback/
│   ├── impact-and-viability--economic-viability--cost-analysis/
│   ├── impact-and-viability--economic-viability--investment-payback/
│   ├── optimize-my-design--panel-type-tradeoff/
│   ├── optimize-my-design--surface-prioritization/
│   ├── optimize-my-design--envelope-simplification/
│   └── optimize-my-design--construction-and-integration/
│
└── configuration/
    └── skills-index.json         ← Decision tree structure, tooltips, skill metadata
```

Each `SKILL.md` defines one analysis: what question it answers, which CEA files it reads, how it computes results, and how the LLM should present the output across the three output modes.

---

## Decision tree

```
Site Potential
 ├── Solar Availability
 │    ├── Surface Irradiation
 │    └── Temporal Availability
 │         ├── Seasonal Patterns
 │         └── Daily Patterns
 ├── Envelope Suitability
 ├── Massing & Shading Strategy
 └── Contextual Feasibility
      ├── Infrastructure Readiness
      ├── Regulatory Constraints
      └── Basic Economic Signal

Performance Estimation
 ├── Energy Generation
 └── Self Sufficiency

Impact and Viability
 ├── Carbon Impact
 │    ├── Operational Carbon Footprint
 │    └── Carbon Payback Period
 └── Economic Viability
      ├── Cost Analysis
      └── Investment Payback

Optimize My Design
 ├── Panel Type Trade-off
 ├── Surface Prioritisation
 ├── Envelope Simplification
 └── Construction & Integration
```

---

## Running locally

```bash
git clone https://github.com/ipekmertan/bipv-llm-pipeline.git
cd bipv-llm-pipeline
pip install -r requirements.txt

# Add your Anthropic API key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml and add your key

streamlit run app.py
```

---

## Tech stack

- **Frontend & backend:** [Streamlit](https://streamlit.io)
- **LLM:** Claude (Anthropic API) via `claude-sonnet-4-20250514`
- **Data processing:** pandas
- **Hosting:** Hugging Face Spaces
- **Simulation data source:** [City Energy Analyst (CEA4)](https://github.com/architecture-building-systems/CityEnergyAnalyst)

---

## Context

This tool is developed as part of a Master of Advanced Studies thesis at ETH Zürich, exploring how LLM-assisted pipelines can make urban building energy simulation more accessible and actionable for architects in early design stages.
