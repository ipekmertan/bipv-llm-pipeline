import streamlit as st
import zipfile
import json
import os
import io
import tempfile
import pandas as pd
from pathlib import Path
import requests
import sys
sys.path.append(str(Path(__file__).parent / "scripts"))
from threshold_module import get_threshold_check, THRESHOLD_RELEVANT_SKILLS

# Map each skill to the simulations whose parameters need checking
SKILL_SIMULATION_MAP = {
    "site-potential--solar-availability--surface-irradiation": ["solar_irradiation"],
    "site-potential--solar-availability--temporal-availability--seasonal-patterns": ["solar_irradiation"],
    "site-potential--solar-availability--temporal-availability--daily-patterns": ["solar_irradiation"],
    "site-potential--envelope-suitability": ["solar_irradiation"],
    "site-potential--massing-and-shading-strategy": ["solar_irradiation"],
    "performance-estimation--energy-generation": ["pv"],
    "optimize-my-design--panel-type-tradeoff": ["pv"],
    "optimize-my-design--surface-prioritization": ["pv"],
    "optimize-my-design--envelope-simplification": ["pv"],
    "optimize-my-design--construction-and-integration": ["pv"],
    "performance-estimation--self-sufficiency": ["pv", "demand"],
    "impact-and-viability--carbon-impact--operational-carbon-footprint": ["pv", "demand"],
    "impact-and-viability--carbon-impact--carbon-payback": ["pv", "demand"],
    "impact-and-viability--economic-viability--cost-analysis": ["pv", "demand"],
    "impact-and-viability--economic-viability--investment-payback": ["pv", "demand"],
    "site-potential--contextual-feasibility--infrastructure-readiness": [],
    "site-potential--contextual-feasibility--regulatory-constraints": [],
    "site-potential--contextual-feasibility--basic-economic-signal": [],
}

st.set_page_config(page_title="BIPV Analyst", page_icon="☀️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Inter', serif; }
.info-box { background:#fffbf0;border-left:3px solid #c8a96e;padding:.8rem 1rem;border-radius:0 8px 8px 0;margin:1rem 0;font-size:.88rem; }
.bubble-user { background:#2d3142;color:white;border-radius:18px 18px 4px 18px;padding:.8rem 1.1rem;margin:.5rem 0 .5rem auto;max-width:75%;width:fit-content;float:right;clear:both; }
.bubble-ai { background:white;border:1px solid #e8e4dc;border-radius:18px 18px 18px 4px;padding:.8rem 1.1rem;margin:.5rem auto .5rem 0;max-width:85%;width:fit-content;float:left;clear:both;line-height:1.65; }
.clearfix { clear:both; }
.param-box-red { background:#fff0f0;border:1px solid #ffcccc;border-radius:8px;padding:14px 16px;font-size:13px;color:#444;line-height:1.5; }
.param-box-green { background:#f0fff4;border:1px solid #b2dfdb;border-radius:8px;padding:14px 16px;font-size:13px;color:#444;line-height:1.5; }
.param-warning { background:#c0392b;color:white;border-radius:8px;padding:14px 16px;font-size:13px;line-height:1.6;margin-top:8px; }
.param-ok { background:#f0fff4;border:1px solid #b2dfdb;border-radius:8px;padding:14px 16px;font-size:13px;color:#2e7d52;margin-top:8px; }
.cluster-counter { background:white;border:1px solid #e0dcd4;border-radius:8px;padding:8px 14px;font-size:13px;color:#444;margin-bottom:8px; }
</style>
""", unsafe_allow_html=True)

SKILLS_INDEX_PATH = Path(__file__).parent / "configuration" / "skills-index.json"
SKILLS_DIR = Path(__file__).parent / "skills"

@st.cache_data
def load_skills_index():
    with open(SKILLS_INDEX_PATH) as f:
        return json.load(f)["skills"]

@st.cache_data(ttl=3600)
def load_acacia_curves():
    local = Path(__file__).parent / "scripts" / "static_curve_data.json"
    with open(local) as f:
        return json.load(f)

def load_skill_md(skill_id, max_chars=3000):
    """Load skill spec, truncating to keep payload within Groq limits."""
    for folder in SKILLS_DIR.iterdir():
        if folder.name.strip() == skill_id:
            md = folder / "SKILL.md"
            if md.exists():
                text = md.read_text()
                if len(text) <= max_chars:
                    return text
                # Keep the Purpose and Output Modes sections — most LLM-relevant
                # Cut at max_chars but try to end at a section boundary
                truncated = text[:max_chars]
                last_section = truncated.rfind("\n## ")
                if last_section > max_chars * 0.5:
                    truncated = truncated[:last_section]
                return truncated + "\n\n[Skill spec truncated for brevity]"
    return ""

def get_building_names(cea_data):
    df = cea_data["files"].get("solar_irradiation_annually_buildings.csv")
    if df is not None and "name" in df.columns:
        return sorted(df["name"].tolist())
    df = cea_data["files"].get("PV_PV1_total_buildings.csv")
    if df is not None and "name" in df.columns:
        return sorted(df["name"].tolist())
    return []

def extract_cea_zip(uploaded_file):
    result = {"files": {}, "available_simulations": [], "errors": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:
            zf.extractall(tmpdir)
        root = Path(tmpdir)
        top = [d for d in root.iterdir() if d.is_dir()]
        if not top: return result
        scenario = top[0]

        export_dir = scenario / "export" / "results"
        if export_dir.exists():
            summaries = sorted([d for d in export_dir.iterdir() if d.is_dir()], reverse=True)
            if summaries:
                latest = summaries[0]
                for fname in ["solar_irradiation_annually.csv","solar_irradiation_annually_buildings.csv",
                              "solar_irradiation_seasonally.csv","solar_irradiation_seasonally_buildings.csv",
                              "solar_irradiation_daily.csv","solar_irradiation_hourly.csv"]:
                    fpath = latest / "solar_irradiation" / fname
                    if fpath.exists():
                        try: result["files"][fname] = pd.read_csv(fpath)
                        except: pass
                for fname in ["demand_annually.csv","demand_annually_buildings.csv","demand_seasonally.csv"]:
                    fpath = latest / "demand" / fname
                    if fpath.exists():
                        try: result["files"][fname] = pd.read_csv(fpath)
                        except: pass

        pv_dir = scenario / "outputs" / "data" / "potentials" / "solar"
        if pv_dir.exists():
            for fpath in sorted(pv_dir.glob("PV_*_total*.csv")):
                try: result["files"][fpath.name] = pd.read_csv(fpath)
                except: pass
            for fpath in sorted(pv_dir.glob("PVT_*_total*.csv")):
                try: result["files"][fpath.name] = pd.read_csv(fpath)
                except: pass

        demand_dir = scenario / "outputs" / "data" / "demand"
        if demand_dir.exists():
            for fpath in demand_dir.glob("*.csv"):
                try: result["files"][fpath.name] = pd.read_csv(fpath)
                except: pass

        fpath = scenario / "inputs" / "database" / "COMPONENTS" / "CONVERSION" / "PHOTOVOLTAIC_PANELS.csv"
        if fpath.exists():
            try: result["files"]["PHOTOVOLTAIC_PANELS.csv"] = pd.read_csv(fpath)
            except: pass

        grid = scenario / "inputs" / "database" / "COMPONENTS" / "FEEDSTOCKS" / "FEEDSTOCKS_LIBRARY" / "GRID.csv"
        if grid.exists():
            try: result["files"]["GRID.csv"] = pd.read_csv(grid)
            except: pass

        epw = scenario / "inputs" / "weather" / "weather.epw"
        if epw.exists():
            try:
                with open(epw, "r", errors="ignore") as f:
                    result["files"]["weather_header"] = f.readline().strip()
            except: pass

        sims = []
        if "solar_irradiation_annually.csv" in result["files"]: sims.append("Solar Irradiation")
        if any(k.startswith("PV_") for k in result["files"]): sims.append("PV Yield")
        if any(k.startswith("PVT_") for k in result["files"]): sims.append("PVT Yield")
        if "demand_annually.csv" in result["files"]: sims.append("Demand")
        result["available_simulations"] = sims

        pv_types_run = [p for p in ["PV1","PV2","PV3","PV4"]
                        if f"PV_{p}_total.csv" in result["files"]]
        pv_config = {"pv_types": pv_types_run, "panel_on_roof": None, "panel_on_wall": None}
        for ptype in pv_types_run:
            df = result["files"].get(f"PV_{ptype}_total_buildings.csv")
            if df is not None and not df.empty:
                roof_area = df.get("PV_roofs_top_m2", pd.Series([0])).sum()
                wall_area = sum(df.get(f"PV_walls_{d}_m2", pd.Series([0])).sum()
                               for d in ["north","south","east","west"])
                pv_config["panel_on_roof"] = bool(roof_area > 0)
                pv_config["panel_on_wall"] = bool(wall_area > 0)
                break

        sc = 0.5
        if pv_types_run:
            import numpy as np
            pv_df = result["files"].get(f"PV_{pv_types_run[0]}_total.csv")
            if pv_df is not None:
                gen_col = next((c for c in pv_df.columns if "E_PV_gen" in c or "E_PV" in c), None)
                if gen_col:
                    total_gen = pv_df[gen_col].sum()
                    demand_dfs = [df for fname, df in result["files"].items()
                                  if fname.startswith("B") and fname.endswith(".csv")
                                  and len(fname) <= 10 and "E_sys_kWh" in df.columns]
                    if demand_dfs and total_gen > 0:
                        demand_series = sum(df["E_sys_kWh"].values for df in demand_dfs)
                        if hasattr(demand_series, "__len__") and len(demand_series) == len(pv_df):
                            sc = round(float(np.minimum(pv_df[gen_col].values, demand_series).sum() / total_gen), 3)
        pv_config["self_consumption"] = sc
        result["pv_config"] = pv_config
    return result


# ── FIX 1: Compact CSV summaries — no raw rows sent to LLM ────────────────────
def summarize_dataframe(fname, df, selected_buildings=None):
    """Extract key statistics from a dataframe instead of sending raw rows."""
    if selected_buildings and "name" in df.columns:
        df = df[df["name"].isin(selected_buildings)]

    n_rows = df.shape[0]
    cols = ", ".join(df.columns)

    # Solar irradiation files — extract ALL surface columns by orientation
    if "solar_irradiation" in fname:
        lines = [f"### {fname} ({n_rows} rows)"]
        surface_cols = {
            "roof":       next((c for c in df.columns if "roof" in c.lower() and "window" not in c.lower()), None),
            "wall_south": next((c for c in df.columns if "south" in c.lower() and "window" not in c.lower()), None),
            "wall_east":  next((c for c in df.columns if "east" in c.lower() and "window" not in c.lower()), None),
            "wall_west":  next((c for c in df.columns if "west" in c.lower() and "window" not in c.lower()), None),
            "wall_north": next((c for c in df.columns if "north" in c.lower() and "window" not in c.lower()), None),
        }
        found = {k: v for k, v in surface_cols.items() if v is not None}
        if found:
            lines.append("Surface irradiation by orientation (kWh/yr, windows excluded):")
            for surface, col in found.items():
                lines.append(f"  {surface}: total={df[col].sum():.0f} kWh | mean={df[col].mean():.0f} kWh")
            if "name" in df.columns and found:
                first_col = list(found.values())[0]
                top3 = df.nlargest(3, first_col)[["name"] + list(found.values())]
                lines.append("Top 3 buildings:")
                for _, r in top3.iterrows():
                    vals = " | ".join(f"{s}={r[c]:.0f}" for s, c in found.items())
                    lines.append(f"  {r['name']}: {vals}")
        else:
            rad_col = next((c for c in df.columns if "kWh" in c or "irr" in c.lower()), None)
            if rad_col:
                lines.append(f"Total: {df[rad_col].sum():.0f} | Mean: {df[rad_col].mean():.0f} kWh")
        return "\n".join(lines)

    # PV yield files
    if fname.startswith("PV_") and "_total" in fname:
        gen_col = next((c for c in df.columns if "E_PV_gen" in c or "E_PV" in c), None)
        area_col = next((c for c in df.columns if "area" in c.lower() or "_m2" in c.lower()), None)
        lines = [f"### {fname} ({n_rows} rows)"]
        if gen_col:
            lines.append(f"Total yield: {df[gen_col].sum():.0f} kWh/yr | "
                        f"Mean per building: {df[gen_col].mean():.0f} kWh/yr | "
                        f"Max: {df[gen_col].max():.0f} kWh/yr")
        if area_col:
            lines.append(f"Total area: {df[area_col].sum():.0f} m²")
        if "name" in df.columns and gen_col:
            top3 = df.nlargest(3, gen_col)[["name", gen_col]]
            lines.append("Top 3: " + "; ".join(f"{r['name']}: {r[gen_col]:.0f} kWh" for _, r in top3.iterrows()))
        return "\n".join(lines)

    # Individual building demand files (B1000.csv etc.)
    if fname.startswith("B") and fname.endswith(".csv") and len(fname) <= 10:
        demand_col = next((c for c in df.columns if "E_sys" in c or "GRID" in c), None)
        pv_col = next((c for c in df.columns if "E_PV" in c), None)
        lines = [f"### {fname} — building demand ({len(df)} hourly rows)"]
        if demand_col:
            lines.append(f"Annual demand: {df[demand_col].sum():.0f} kWh | Peak hour: {df[demand_col].max():.1f} kWh")
        if pv_col:
            lines.append(f"Annual PV gen: {df[pv_col].sum():.0f} kWh")
        lines.append(f"Columns: {', '.join(df.columns[:10])}{'...' if len(df.columns) > 10 else ''}")
        return "\n".join(lines)

    # Demand files
    if "demand" in fname.lower() or fname == "Total_demand.csv":
        demand_col = next((c for c in df.columns if "E_sys" in c or "GRID" in c or "total" in c.lower()), None)
        lines = [f"### {fname} ({n_rows} rows)"]
        if demand_col:
            lines.append(f"Total demand: {df[demand_col].sum():.0f} kWh/yr | "
                        f"Mean: {df[demand_col].mean():.0f} kWh/yr | "
                        f"Max: {df[demand_col].max():.0f} kWh/yr")
        else:
            lines.append(f"Columns: {cols}")
        return "\n".join(lines)

    # PHOTOVOLTAIC_PANELS.csv — send full (it's small reference data)
    if fname == "PHOTOVOLTAIC_PANELS.csv":
        return f"### {fname}\n{df.to_csv(index=False)}"

    # GRID.csv — send full (it's tiny)
    if fname == "GRID.csv":
        return f"### {fname}\n{df.to_csv(index=False)}"

    # Fallback — schema only, no rows
    return f"### {fname} ({n_rows} rows)\nColumns: {cols}"


def build_data_summary(cea_data, selected_buildings=None, scale="District"):
    lines = []
    if "weather_header" in cea_data["files"]:
        lines.append(f"## Location\n{cea_data['files']['weather_header']}\n")
    lines.append(f"## Available simulations\n{', '.join(cea_data['available_simulations'])}\n")
    lines.append(f"## Analysis scale\n{scale}\n")
    if selected_buildings:
        lines.append(f"## Selected buildings\n{', '.join(selected_buildings)}\n")

    pv_types_relevant = any(k.startswith("PV_PV") for k in (cea_data.get("files") or {}))

    # FIX 1 applied: use summarize_dataframe instead of df.head(10).to_csv()
    for fname in ["solar_irradiation_annually.csv","solar_irradiation_annually_buildings.csv",
                  "solar_irradiation_seasonally.csv","demand_annually.csv",
                  "PV_PV1_total.csv","PV_PV2_total.csv","PV_PV3_total.csv","PV_PV4_total.csv",
                  "PHOTOVOLTAIC_PANELS.csv","GRID.csv","Total_demand.csv"]:
        df = cea_data["files"].get(fname)
        if df is not None:
            lines.append(summarize_dataframe(fname, df, selected_buildings=selected_buildings))

    # Include individual building demand files — filter to selected if applicable
    building_demand_files = sorted([
        fname for fname in cea_data["files"]
        if fname.startswith("B") and fname.endswith(".csv") and len(fname) <= 10
    ])
    if selected_buildings:
        building_demand_files = [f for f in building_demand_files
                                 if f.replace(".csv", "") in selected_buildings]
    for fname in building_demand_files:
        df = cea_data["files"].get(fname)
        if df is not None:
            lines.append(summarize_dataframe(fname, df))

    pv_config = cea_data.get("pv_config", {})
    if pv_config and pv_types_relevant:
        config_lines = ["### PV Simulation Configuration (inferred from outputs)"]
        if pv_config.get("pv_types"):
            config_lines.append(f"Panel types simulated: {', '.join(pv_config['pv_types'])}")
        if pv_config.get("panel_on_roof") is not None:
            roof_status = "YES" if pv_config["panel_on_roof"] else "NO — roof surfaces excluded"
            config_lines.append(f"panel-on-roof: {roof_status}")
        if pv_config.get("panel_on_wall") is not None:
            wall_status = "YES" if pv_config["panel_on_wall"] else "NO — wall/facade surfaces excluded"
            config_lines.append(f"panel-on-wall: {wall_status}")
        lines.append("\n".join(config_lines))

    return "\n".join(lines)


def call_llm(system_prompt, messages):
    import time
    api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    # Use 8b-instant for all modes — much higher Groq free tier rate limit
    model = "llama-3.1-8b-instant"
    max_retries = 4
    retry_delays = [15, 30, 45, 60]  # seconds between retries
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 1500,
                      "messages": [{"role": "system", "content": system_prompt}] + messages},
                timeout=60
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429 and attempt < max_retries - 1:
                wait = retry_delays[attempt]
                with st.spinner(f"Rate limit hit — waiting {wait}s before retry ({attempt + 1}/{max_retries - 1})…"):
                    time.sleep(wait)
                continue
            return f"⚠️ API error: {e}"
        except Exception as e:
            return f"⚠️ API error: {e}"


def build_system_prompt(skill_md, cea_summary, output_mode, scale, selected_buildings=None):
    building_context = ""
    if selected_buildings:
        building_context = f"\nFocus your analysis specifically on: {', '.join(selected_buildings)}."

    mode_instructions = {
        "Key takeaway": """OUTPUT MODE: Key takeaway — STRICT RULES:
- Maximum 3 sentences. No exceptions.
- Sentence 1 — Lead with the best-performing surface or result: name it, give the specific number, and say why it matters. Start with the surface/finding, not the building name. Example: "The roof of B1000 receives 1,613,514 kWh/yr — well above the viability threshold."
- Sentence 2 — One comparison or context sentence that helps the architect understand the scale or ranking.
- Sentence 3 — One concrete, specific design action the architect should take. Include actual numbers where possible (area, percentage, kWh target). Never say "maximise" without saying what to maximise to. Example: "Prioritise full roof coverage (~500 m²) before considering facade surfaces."
- DO NOT use numbered lists or labels like "1." "2." "Headline:" "Context:" — just write the sentences directly.
- DO NOT be vague — every sentence must contain a specific number or named surface.
- You MAY use **bold** for the key number or surface name to aid readability.""",

        "Explain the numbers": """OUTPUT MODE: Explain the numbers — RULES:
- Walk through the key numbers clearly, one at a time.
- You may use bullet points with values and brief explanations.
- Keep each point to 1-2 sentences maximum.
- Do not exceed 200 words total.
- No hypothetical assumptions — only use actual data provided.""",

        "Design implication": """OUTPUT MODE: Design implication — RULES:
- Skip the numbers entirely unless one is essential to make a point.
- Focus only on what this means for the architect's design decisions.
- Maximum 4 sentences.
- Frame every sentence as an actionable insight or trade-off.
- DO NOT show calculations or methodology."""
    }

    mode_block = mode_instructions.get(output_mode, f"Output mode: {output_mode}")

    return f"""You are a BIPV expert helping architects interpret CEA4 simulation results.
Scale: {scale}{building_context}

{mode_block}

## Skill specification
{skill_md}

## CEA data
{cea_summary}

Use actual numbers from the data where available. If a specific value is missing, note it briefly in one sentence, then proceed using industry-standard defaults clearly labelled as estimates — e.g. grid emissions ~0.4 kgCO₂/kWh for Central Europe, panel cost ~250 €/m², system lifetime 25 years, performance ratio 0.75.
Do NOT describe, mention, or suggest visualizations or charts — these are generated automatically by the app.
Do NOT use markdown headers (#), bullet points (-), or numbered lists. You MAY use **bold** sparingly for key numbers and surface names."""

    # Cap total prompt size to avoid 413 errors
    max_total = 6000
    prompt = f"""You are a BIPV expert helping architects interpret CEA4 simulation results.
Scale: {scale}{building_context}

{mode_block}

## Skill specification
{skill_md[:2000]}

## CEA data
{cea_summary[:3000]}

Use actual numbers from the data where available. If a specific value is missing, note it briefly in one sentence, then proceed using industry-standard defaults clearly labelled as estimates — e.g. grid emissions ~0.4 kgCO₂/kWh for Central Europe, panel cost ~250 €/m², system lifetime 25 years, performance ratio 0.75.
Do NOT describe, mention, or suggest visualizations or charts — these are generated automatically by the app.
Do NOT use markdown headers (#), bullet points (-), or numbered lists. You MAY use **bold** sparingly for key numbers and surface names."""
    return prompt


def render_parameter_check(threshold_result, skill_id):
    if not threshold_result or threshold_result.get("error"):
        return

    simulations = SKILL_SIMULATION_MAP.get(skill_id, None)

    if simulations is not None and len(simulations) == 0:
        st.markdown(
            '<div style="background:#f5f5f5;border:1px solid #e0e0e0;border-radius:8px;'
            'padding:10px 14px;font-size:12.5px;color:#888;margin-bottom:12px;">'
            'No parameter check needed for this analysis.</div>',
            unsafe_allow_html=True
        )
        return

    city = threshold_result["location"]["city"]
    country = threshold_result["country"]
    em_grid = threshold_result["em_grid"]
    thresholds = threshold_result.get("thresholds_by_panel", {})

    if simulations is not None and "pv" not in simulations:
        st.markdown(
            '<div style="background:#f0fff4;border:1px solid #b2dfdb;border-radius:8px;'
            'padding:10px 14px;font-size:12.5px;color:#2e7d52;margin-bottom:12px;">'
            '✓ All parameter inputs look correct for this analysis.</div>',
            unsafe_allow_html=True
        )
        return

    cea_data = st.session_state.get("cea_data", {})
    available_files = cea_data.get("files", {}) if cea_data else {}
    run_pv_types = [
        ptype for ptype in ["PV1", "PV2", "PV3", "PV4"]
        if f"PV_{ptype}_total.csv" in available_files
    ]
    if not run_pv_types:
        run_pv_types = list(thresholds.keys()) if thresholds else ["PV1"]

    from threshold_module import PV_PANEL_TYPES

    thresholds_uncapped = threshold_result.get("thresholds_uncapped", {})
    type_thresholds = {p: thresholds.get(p, 1200) for p in run_pv_types}
    type_thresholds_uncapped = {p: thresholds_uncapped.get(p, 1200) for p in run_pv_types}

    max_ptype = max(type_thresholds, key=lambda p: type_thresholds[p])
    recommended = type_thresholds[max_ptype]
    driving_panel = PV_PANEL_TYPES.get(max_ptype, {})

    if len(run_pv_types) == 1:
        sim_label = f'Photovoltaic simulation<br><span style="font-size:11px;color:#999;">{run_pv_types[0]} — {PV_PANEL_TYPES.get(run_pv_types[0], {}).get("description", "")}</span>'
    else:
        types_str = ", ".join([f"{p} ({PV_PANEL_TYPES.get(p,{}).get('description','')})" for p in run_pv_types])
        sim_label = f'Photovoltaic simulation<br><span style="font-size:11px;color:#999;">{types_str}</span>'

    pr_label = threshold_result.get("pr_label", "PR 0.75")
    if len(run_pv_types) == 1:
        raw = int(type_thresholds_uncapped.get(run_pv_types[0], recommended))
        cap = int(recommended)
        if raw == cap:
            info_text = (
                f'In <b>{city}, {country}</b> (grid: {em_grid} kgCO&#x2082;/kWh), '
                f'the annual radiation threshold is <b>{raw} kWh/m&#x00B2;/year</b>.'
            )
        else:
            info_text = (
                f'In <b>{city}, {country}</b> (grid: {em_grid} kgCO&#x2082;/kWh), '
                f'the annual radiation threshold is {raw} kWh/m&#x00B2;/year '
                f'— but that would exclude almost every surface in practice, '
                f'so it is capped at <b>{cap} kWh/m&#x00B2;/year</b>.'
            )
    else:
        raw_strictest = int(type_thresholds_uncapped.get(max_ptype, recommended))
        cap_strictest = int(recommended)
        if raw_strictest == cap_strictest:
            info_text = (
                f'In <b>{city}, {country}</b> (grid: {em_grid} kgCO&#x2082;/kWh), '
                f'the annual radiation threshold is <b>{raw_strictest} kWh/m&#x00B2;/year</b>.'
            )
        else:
            info_text = (
                f'In <b>{city}, {country}</b> (grid: {em_grid} kgCO&#x2082;/kWh), '
                f'the annual radiation threshold is {raw_strictest} kWh/m&#x00B2;/year '
                f'— but that would exclude almost every surface in practice, '
                f'so it is capped at <b>{cap_strictest} kWh/m&#x00B2;/year</b>.'
            )

    st.markdown("**Parameter check**")

    h1, h2, h3, h4 = st.columns([2.5, 2, 2, 4])
    for col, label in zip([h1, h2, h3, h4], ["Simulation", "Parameter", "Recommended value", "Info"]):
        with col:
            st.markdown(
                f'<p style="font-size:11px;font-weight:600;color:#888;letter-spacing:0.08em;'
                f'text-transform:uppercase;margin:0;">{label}</p>',
                unsafe_allow_html=True
            )
    st.markdown('<hr style="margin:4px 0 8px 0;border:none;border-top:1.5px solid #e0e0e0;">', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([2.5, 2, 2, 4])
    with c1:
        st.markdown(sim_label, unsafe_allow_html=True)
    with c2:
        st.markdown("`annual-radiation-threshold`")
    with c3:
        status = "unverifiable"
        tooltip = "Cannot verify — check this value in CEA"
        if status == "wrong":
            bg, border = "#fff0f0", "#ffcccc"
        elif status == "correct":
            bg, border = "#f0fff4", "#b2dfdb"
        else:
            bg, border = "#e3f2fd", "#90caf9"
        st.markdown(
            f'<div style="background:{bg};border:1px solid {border};border-radius:6px;'
            f'padding:6px 10px;font-size:13px;cursor:default;" '
            f'title="{tooltip}">'
            f'<b>{int(recommended)} kWh/m&#x00B2;/year</b></div>',
            unsafe_allow_html=True
        )
    with c4:
        st.markdown(info_text, unsafe_allow_html=True)
        if st.button(
            "Reasoning →" if not st.session_state.get("reasoning_threshold") else "Reasoning ↑",
            key="btn_threshold"
        ):
            st.session_state["reasoning_threshold"] = not st.session_state.get("reasoning_threshold", False)
            st.rerun()

        if st.session_state.get("reasoning_threshold"):
            if len(run_pv_types) > 1:
                panel_table = "".join([
                    f'<tr><td style="padding:2px 8px;">{p}</td>'
                    f'<td style="padding:2px 8px;">{PV_PANEL_TYPES.get(p,{}).get("description","")}</td>'
                    f'<td style="padding:2px 8px;">{PV_PANEL_TYPES.get(p,{}).get("em_bipv","")} kgCO&#x2082;/m&#x00B2;</td>'
                    f'<td style="padding:2px 8px;"><b>{int(type_thresholds[p])} kWh/m&#x00B2;/yr</b></td></tr>'
                    for p in run_pv_types
                ])
                panel_section = (
                    f'<p style="font-size:12px;margin:8px 0 4px 0;"><strong>Thresholds by panel type:</strong></p>'
                    f'<table style="font-size:11px;color:#555;border-collapse:collapse;">'
                    f'<tr style="color:#999;"><td style="padding:2px 8px;">Type</td><td style="padding:2px 8px;">Technology</td>'
                    f'<td style="padding:2px 8px;">Embodied carbon</td><td style="padding:2px 8px;">Threshold</td></tr>'
                    f'{panel_table}</table>'
                )
            else:
                panel_section = ""

            st.markdown(
                f'<div style="background:#f7f7f7;border:1px solid #e8e8e8;border-radius:8px;'
                f'padding:12px 14px;margin-top:8px;font-size:12px;color:#555;line-height:1.7;">'
                f'Every surface needs a minimum amount of sunlight to make BIPV worthwhile. '
                f'Below this level, the panel never generates enough clean electricity to offset '
                f'the carbon emitted when it was manufactured. '
                f'For <strong>{country}</strong> (grid: {em_grid} kgCO&#x2082;/kWh) — '
                f'the cleaner the grid, the harder panels are to justify on carbon grounds, '
                f'so a cleaner grid means a higher threshold. '
                f'When the raw threshold exceeds 1200 kWh/m&#x00B2;/year it is capped there, '
                f'because beyond that almost no real surface qualifies and the value becomes impractical. '
                f'CEA\'s default of 800 kWh/m&sup2;/year was set for carbon-intensive grids '
                f'like Southeast Asia and is often too low for Europe.'
                f'{panel_section}'
                f'</div>',
                unsafe_allow_html=True
            )

            acacia_curves = threshold_result.get("acacia_curves", {})
            if acacia_curves:
                import altair as alt
                panel_options = [p for p in run_pv_types if p in acacia_curves]
                if not panel_options:
                    panel_options = list(acacia_curves.keys())[:1]
                selected_curve_panel = st.radio(
                    "Panel type",
                    options=panel_options,
                    format_func=lambda p: f"{p} — {PV_PANEL_TYPES.get(p,{}).get('description', p)}",
                    horizontal=True,
                    key="curve_panel_toggle"
                )
                curve = acacia_curves.get(selected_curve_panel)
                if curve is not None:
                    irr = [float(x) for x in curve["irradiance"]]
                    imp = [float(x) for x in curve["impact"]]
                    chart_df = pd.DataFrame({"irradiance": irr, "impact": imp})
                    chart_df = chart_df[(chart_df["irradiance"] <= 1000) & (chart_df["impact"] >= 0)]
                    y_max = min(float(chart_df["impact"].iloc[0]) * 1.05, 2.0)
                    line = alt.Chart(chart_df).mark_line(color="#c07800", strokeWidth=2).encode(
                        x=alt.X("irradiance:Q", title="Annual irradiance (kWh/sqm/a)", scale=alt.Scale(domain=[0, 1000])),
                        y=alt.Y("impact:Q", title="Device intensity (kgCO2e/kWh)", scale=alt.Scale(domain=[0, y_max]))
                    )
                    grid_df = pd.DataFrame({"y": [float(em_grid)]})
                    grid_line = alt.Chart(grid_df).mark_rule(color="black", strokeWidth=1.5).encode(
                        y=alt.Y("y:Q", scale=alt.Scale(domain=[0, y_max]))
                    )
                    chart = (line + grid_line).properties(height=220).configure_axis(
                        grid=True, gridColor="#e0e0e0", gridDash=[4, 4]
                    ).configure_view(strokeWidth=0)
                    st.altair_chart(chart, use_container_width=True)
                    st.markdown(
                        '<span style="font-size:11px;color:#aaa;font-style:italic;">'
                        'Source: <a href="https://acacia.arch.ethz.ch/calculator" target="_blank" '
                        'style="color:#aaa;">acacia.arch.ethz.ch/calculator</a></span>',
                        unsafe_allow_html=True
                    )

            st.markdown(
                f'<span style="font-size:11px;color:#aaa;margin-top:6px;display:block;font-style:italic;">'
                f'Happle et al. (2019). J. Phys.: Conf. Ser. 1343, 012077. &bull; '
                f'Galimshina et al. (2024). Renew. Energy 236, 121404. &bull; '
                f'McCarty et al. (2025a). RSER 211, 115326. &bull; '
                f'McCarty et al. (2025b). J. Phys.: Conf. Ser. 3140, 032006.</span>',
                unsafe_allow_html=True
            )

    st.markdown('<hr style="margin:4px 0;border:none;border-top:1px solid #f0f0f0;">', unsafe_allow_html=True)


def build_tree():
    tree = {}
    for s in skills:
        path = s["position_in_tree"]
        goal = path[0]
        if goal not in tree: tree[goal] = {}
        if len(path) == 2:
            tree[goal][path[1]] = {"id": s["id"], "children": {}}
        elif len(path) == 3:
            mid = path[1]
            if mid not in tree[goal]: tree[goal][mid] = {"id": None, "children": {}}
            tree[goal][mid]["children"][path[2]] = {"id": s["id"], "children": {}}
        elif len(path) == 4:
            mid, sub = path[1], path[2]
            if mid not in tree[goal]: tree[goal][mid] = {"id": None, "children": {}}
            if sub not in tree[goal][mid]["children"]:
                tree[goal][mid]["children"][sub] = {"id": None, "children": {}}
            tree[goal][mid]["children"][sub]["children"][path[3]] = {"id": s["id"], "children": {}}
    return tree

skills = load_skills_index()
TREE = build_tree()

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("cea_data", None), ("chat_history", []),
              ("tree_scale", None), ("tree_goal", None), ("tree_sub", None),
              ("tree_subsub", None), ("tree_mode", None),
              ("skill_id", None), ("skill_name", None),
              ("analysis_ran", False), ("threshold_result", None),
              ("param_check_hidden", False),
              ("selected_building", None), ("selected_cluster", []),
              ("reasoning_open", False), ("reasoning_threshold", False),
              ("cached_system_prompt", None), ("tree_subsubsub", None)]:   # FIX 2: cache slot
    if k not in st.session_state:
        st.session_state[k] = v

# ── Upload screen ──────────────────────────────────────────────────────────────
if st.session_state.cea_data is None:
    st.markdown("# BIPV Analyst")
    st.markdown("Upload your CEA4 project folder (zipped) to begin.")
    st.markdown('<div class="info-box"><strong>How to export:</strong> Compress your CEA scenario folder (e.g. <code>baseline</code>) to a <code>.zip</code> and upload it here.</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Drop your CEA project zip here", type=["zip"], label_visibility="collapsed")
    if uploaded:
        with st.spinner("Reading project…"):
            cea_data = extract_cea_zip(uploaded)
        if not cea_data["files"]:
            st.error("No simulation files found.")
        else:
            st.session_state.cea_data = cea_data
            st.session_state.param_check_hidden = False
            if "weather_header" in cea_data["files"]:
                st.session_state.threshold_result = get_threshold_check(
                    cea_data["files"]["weather_header"], cea_default=800,
                    self_consumption=cea_data.get("pv_config", {}).get("self_consumption", 0.5),
                    acacia_data=load_acacia_curves()
                )
            st.rerun()

# ── Analysis screen ────────────────────────────────────────────────────────────
else:
    with st.container():
        st.markdown("### Build your analysis")
        sims = st.session_state.cea_data["available_simulations"]
        st.caption("Loaded: " + " · ".join(f"✓ {s}" for s in sims))
        st.markdown("")

        # Step 1: Scale
        if st.session_state.tree_scale:
            st.markdown(f"**Scale** · *{st.session_state.tree_scale}*")
        else:
            st.markdown("**Step 1 — Scale**")
            for scale in ["Building", "Cluster", "District"]:
                if st.button(scale, key=f"scale_{scale}"):
                    st.session_state.tree_scale = scale
                    st.session_state.tree_goal = None
                    st.session_state.tree_sub = None
                    st.session_state.tree_subsub = None
                    st.session_state.tree_mode = None
                    st.session_state.analysis_ran = False
                    st.session_state.selected_building = None
                    st.session_state.selected_cluster = []
                    st.session_state.cached_system_prompt = None  # FIX 2: clear cache on new analysis
                    st.rerun()

        # Building / Cluster selector
        if st.session_state.tree_scale in ["Building", "Cluster"]:
            building_names = get_building_names(st.session_state.cea_data)
            if building_names:
                st.markdown("")
                if st.session_state.tree_scale == "Building":
                    st.markdown("**Select building**")
                    chosen = st.selectbox(
                        "Building", building_names,
                        index=building_names.index(st.session_state.selected_building)
                        if st.session_state.selected_building in building_names else 0,
                        label_visibility="collapsed", key="building_selector"
                    )
                    st.session_state.selected_building = chosen
                elif st.session_state.tree_scale == "Cluster":
                    n = len(st.session_state.selected_cluster)
                    st.markdown(
                        f'<div class="cluster-counter">{"No buildings selected yet" if n == 0 else f"{n} building{"s" if n > 1 else ""} selected"}</div>',
                        unsafe_allow_html=True
                    )
                    st.markdown("**Select buildings for cluster**")
                    chosen = st.multiselect(
                        "Buildings", building_names,
                        default=st.session_state.selected_cluster,
                        label_visibility="collapsed", key="cluster_selector"
                    )
                    st.session_state.selected_cluster = chosen

        # Step 2: Goal
        if st.session_state.tree_scale:
            st.markdown("")
            if st.session_state.tree_goal:
                st.markdown(f"**Goal** · *{st.session_state.tree_goal}*")
            else:
                st.markdown("**Step 2 — What do you want to understand?**")
                for goal in TREE.keys():
                    label = goal.replace("Impact and Viability", "Impact & Viability")
                    if st.button(label, key=f"goal_{goal}"):
                        st.session_state.tree_goal = goal
                        st.session_state.tree_sub = None
                        st.session_state.tree_subsub = None
                        st.session_state.tree_mode = None
                        st.session_state.analysis_ran = False
                        st.session_state.cached_system_prompt = None  # FIX 2: clear on new path
                        st.rerun()

        # Step 3: Topic
        if st.session_state.tree_goal:
            st.markdown("")
            topics = TREE[st.session_state.tree_goal]
            if st.session_state.tree_sub:
                st.markdown(f"**Topic** · *{st.session_state.tree_sub}*")
            else:
                st.markdown("**Step 3 — Topic**")
                for topic, node in topics.items():
                    if st.button(topic, key=f"sub_{topic}"):
                        st.session_state.tree_sub = topic
                        st.session_state.tree_subsub = None
                        st.session_state.tree_subsubsub = None
                        st.session_state.tree_mode = None
                        st.session_state.analysis_ran = False
                        st.session_state.cached_system_prompt = None
                        if not node["children"]:
                            st.session_state.skill_id = node["id"]
                            st.session_state.skill_name = topic
                        st.rerun()

        # Step 4: Analysis (depth-3 children)
        if st.session_state.tree_sub:
            node = TREE[st.session_state.tree_goal][st.session_state.tree_sub]
            if node["children"]:
                st.markdown("")
                if st.session_state.tree_subsub:
                    st.markdown(f"**Analysis** · *{st.session_state.tree_subsub}*")
                else:
                    st.markdown("**Step 4 — Analysis**")
                    for child, child_node in node["children"].items():
                        if st.button(child, key=f"subsub_{child}"):
                            st.session_state.tree_subsub = child
                            st.session_state.tree_subsubsub = None
                            st.session_state.tree_mode = None
                            st.session_state.analysis_ran = False
                            st.session_state.cached_system_prompt = None
                            if not child_node["children"]:
                                # leaf — set skill directly
                                st.session_state.skill_id = child_node["id"]
                                st.session_state.skill_name = child
                            st.rerun()

        # Step 4b: Sub-analysis (depth-4 children, e.g. Temporal Availability → Seasonal/Daily)
        if st.session_state.tree_subsub:
            node = TREE[st.session_state.tree_goal][st.session_state.tree_sub]
            child_node = node["children"].get(st.session_state.tree_subsub, {})
            if child_node.get("children"):
                st.markdown("")
                if st.session_state.tree_subsubsub:
                    st.markdown(f"**Sub-analysis** · *{st.session_state.tree_subsubsub}*")
                else:
                    st.markdown("**Step 4b — Sub-analysis**")
                    for grandchild, grandchild_node in child_node["children"].items():
                        if st.button(grandchild, key=f"subsubsub_{grandchild}"):
                            st.session_state.tree_subsubsub = grandchild
                            st.session_state.tree_mode = None
                            st.session_state.analysis_ran = False
                            st.session_state.cached_system_prompt = None
                            st.session_state.skill_id = grandchild_node["id"]
                            st.session_state.skill_name = grandchild
                            st.rerun()

        # Step 5: Output mode
        skill_ready = st.session_state.skill_id and (
            not TREE.get(st.session_state.tree_goal, {}).get(
                st.session_state.tree_sub or "", {}).get("children") or
            st.session_state.tree_subsub
        ) and (
            not (
                st.session_state.tree_subsub and
                TREE.get(st.session_state.tree_goal, {}).get(
                    st.session_state.tree_sub or "", {}).get("children", {}).get(
                    st.session_state.tree_subsub or "", {}).get("children")
            ) or st.session_state.tree_subsubsub
        )
        if skill_ready:
            st.markdown("")
            if st.session_state.tree_mode:
                st.markdown(f"**Output mode** · *{st.session_state.tree_mode}*")
            else:
                st.markdown("**Step 5 — How do you want the answer?**")
                for mode in ["Key takeaway", "Explain the numbers", "Design implication"]:
                    if st.button(mode, key=f"mode_{mode}"):
                        st.session_state.tree_mode = mode
                        st.session_state.analysis_ran = False
                        st.session_state.cached_system_prompt = None
                        st.rerun()

        # Run button
        if st.session_state.tree_mode and st.session_state.skill_id and not st.session_state.analysis_ran:
            scale = st.session_state.tree_scale
            ready_to_run = True
            if scale == "Building" and not st.session_state.selected_building:
                st.warning("Please select a building above.")
                ready_to_run = False
            if scale == "Cluster" and len(st.session_state.selected_cluster) == 0:
                st.warning("Please select at least one building for the cluster.")
                ready_to_run = False

            if ready_to_run:
                st.markdown("")
                if st.button("▶ Run analysis", type="primary"):
                    st.session_state.chat_history = []
                    st.session_state.analysis_ran = True
                    st.rerun()

        st.markdown("---")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("← Go back"):
                if st.session_state.tree_mode:
                    st.session_state.tree_mode = None
                    st.session_state.analysis_ran = False
                elif st.session_state.tree_subsubsub:
                    st.session_state.tree_subsubsub = None
                    st.session_state.skill_id = None
                    st.session_state.skill_name = None
                elif st.session_state.tree_subsub:
                    st.session_state.tree_subsub = None
                    st.session_state.tree_subsubsub = None
                    st.session_state.skill_id = None
                    st.session_state.skill_name = None
                elif st.session_state.tree_sub:
                    st.session_state.tree_sub = None
                    st.session_state.skill_id = None
                    st.session_state.skill_name = None
                elif st.session_state.tree_goal:
                    st.session_state.tree_goal = None
                elif st.session_state.tree_scale:
                    st.session_state.tree_scale = None
                    st.session_state.selected_building = None
                    st.session_state.selected_cluster = []
                st.session_state.chat_history = []
                st.session_state.cached_system_prompt = None
                st.rerun()
        with col_b:
            if st.button("↺ Start over"):
                for k in ["tree_scale","tree_goal","tree_sub","tree_subsub","tree_subsubsub",
                          "tree_mode","skill_id","skill_name","analysis_ran",
                          "selected_building","selected_cluster","cached_system_prompt"]:
                    st.session_state[k] = None if k != "selected_cluster" else []
                st.session_state.chat_history = []
                st.rerun()
        with col_c:
            if st.button("↩ New project"):
                for k in ["cea_data","tree_scale","tree_goal","tree_sub","tree_subsub","tree_subsubsub",
                          "tree_mode","skill_id","skill_name","analysis_ran",
                          "threshold_result","param_check_hidden",
                          "selected_building","selected_cluster","cached_system_prompt"]:
                    st.session_state[k] = None if k != "selected_cluster" else []
                st.session_state.chat_history = []
                st.rerun()

    # ── Analysis section ───────────────────────────────────────────────────────
    st.markdown("---")
    with st.container():
        st.markdown("### Analysis")

        if st.session_state.analysis_ran and st.session_state.skill_id and not st.session_state.chat_history:
            scale = st.session_state.tree_scale
            selected_buildings = None
            if scale == "Building" and st.session_state.selected_building:
                selected_buildings = [st.session_state.selected_building]
            elif scale == "Cluster" and st.session_state.selected_cluster:
                selected_buildings = st.session_state.selected_cluster

            skill_md = load_skill_md(st.session_state.skill_id)
            cea_summary = build_data_summary(
                st.session_state.cea_data,
                selected_buildings=selected_buildings,
                scale=scale
            )
            # FIX 2: Build system prompt once and cache it
            system_prompt = build_system_prompt(
                skill_md, cea_summary,
                st.session_state.tree_mode,
                scale,
                selected_buildings=selected_buildings
            )
            st.session_state.cached_system_prompt = system_prompt

            user_msg = (f"Run the **{st.session_state.skill_name}** analysis at "
                       f"**{scale}** scale in **{st.session_state.tree_mode}** mode."
                       + (f" Focus on buildings: {', '.join(selected_buildings)}." if selected_buildings else "")
                       + " Use only the data provided.")
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            with st.spinner("Analysing…"):
                response = call_llm(system_prompt, st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()

        if not st.session_state.chat_history:
            st.markdown('<div class="info-box">← Complete the steps on the left to run an analysis.</div>',
                       unsafe_allow_html=True)
        elif st.session_state.skill_id and st.session_state.threshold_result:
            render_parameter_check(st.session_state.threshold_result, st.session_state.skill_id)
            st.markdown("**Analysis results**")

        for i, msg in enumerate(st.session_state.chat_history):
            if msg["role"] == "user" and i == 0:
                pass  # hide initial trigger
            elif msg["role"] == "user":
                st.markdown(f'<div class="bubble-user">{msg["content"]}</div><div class="clearfix"></div>',
                           unsafe_allow_html=True)
            else:
                # Render as markdown so formatting works, then inject chart
                st.markdown('<div class="bubble-ai">', unsafe_allow_html=True)
                st.markdown(msg["content"])
                st.markdown('</div><div class="clearfix"></div>', unsafe_allow_html=True)
                # Render chart inline after first AI response only
                if i == 1 and st.session_state.skill_id and st.session_state.cea_data:
                    _scale = st.session_state.tree_scale
                    _sel = None
                    if _scale == "Building" and st.session_state.selected_building:
                        _sel = [st.session_state.selected_building]
                    elif _scale == "Cluster" and st.session_state.selected_cluster:
                        _sel = st.session_state.selected_cluster
                    try:
                        from charts import render_skill_chart
                        _chart = render_skill_chart(
                            st.session_state.skill_id,
                            st.session_state.cea_data,
                            _sel,
                            st.session_state.tree_mode or "Key takeaway"
                        )
                        if _chart is not None:
                            st.altair_chart(_chart, use_container_width=True)
                    except Exception:
                        pass

        if st.session_state.chat_history:
            st.markdown("---")
            followup = st.text_input("Ask a follow-up…", key="fu",
                                    placeholder="e.g. Which building has the best south facade?")
            if st.button("Send") and followup.strip():
                # FIX 2 + FIX 3: use cached system prompt, send only last 4 messages
                system_prompt = st.session_state.get("cached_system_prompt") or ""
                st.session_state.chat_history.append({"role": "user", "content": followup})
                recent_history = st.session_state.chat_history[-4:]  # FIX 3: cap history
                with st.spinner("Thinking…"):
                    response = call_llm(system_prompt, recent_history)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
