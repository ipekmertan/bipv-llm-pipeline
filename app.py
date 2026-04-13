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
    # Solar Irradiation only
    "site-potential--solar-availability--surface-irradiation": ["solar_irradiation"],
    "site-potential--solar-availability--temporal-availability--seasonal-patterns": ["solar_irradiation"],
    "site-potential--solar-availability--temporal-availability--daily-patterns": ["solar_irradiation"],
    "site-potential--envelope-suitability": ["solar_irradiation"],
    "site-potential--massing-and-shading-strategy": ["solar_irradiation"],
    # PV Yield only
    "performance-estimation--energy-generation": ["pv"],
    "optimize-my-design--panel-type-tradeoff": ["pv"],
    "optimize-my-design--surface-prioritization": ["pv"],
    "optimize-my-design--envelope-simplification": ["pv"],
    "optimize-my-design--construction-and-integration": ["pv"],
    # PV + Demand
    "performance-estimation--self-sufficiency": ["pv", "demand"],
    "impact-and-viability--carbon-impact--operational-carbon-footprint": ["pv", "demand"],
    "impact-and-viability--carbon-impact--carbon-payback": ["pv", "demand"],
    "impact-and-viability--economic-viability--cost-analysis": ["pv", "demand"],
    "impact-and-viability--economic-viability--investment-payback": ["pv", "demand"],
    # No parameter check
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

def load_skill_md(skill_id):
    for folder in SKILLS_DIR.iterdir():
        if folder.name.strip() == skill_id:
            md = folder / "SKILL.md"
            if md.exists(): return md.read_text()
    return ""

def get_building_names(cea_data):
    """Extract building names from irradiation buildings file."""
    df = cea_data["files"].get("solar_irradiation_annually_buildings.csv")
    if df is not None and "name" in df.columns:
        return sorted(df["name"].tolist())
    # fallback: try PV buildings file
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

        for fname in ["Total_demand.csv"]:
            fpath = scenario / "outputs" / "data" / "demand" / fname
            if fpath.exists():
                try: result["files"][fname] = pd.read_csv(fpath)
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

        # Infer PV simulation config from output data
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
        result["pv_config"] = pv_config
    return result

def build_data_summary(cea_data, selected_buildings=None, scale="District"):
    lines = []
    if "weather_header" in cea_data["files"]:
        lines.append(f"## Location\n{cea_data['files']['weather_header']}\n")
    lines.append(f"## Available simulations\n{', '.join(cea_data['available_simulations'])}\n")
    lines.append(f"## Analysis scale\n{scale}\n")
    if selected_buildings:
        lines.append(f"## Selected buildings\n{', '.join(selected_buildings)}\n")

    pv_types_relevant = any(k.startswith("PV_PV") for k in (cea_data.get("files") or {}))
    for fname in ["solar_irradiation_annually.csv","solar_irradiation_annually_buildings.csv",
                  "solar_irradiation_seasonally.csv","demand_annually.csv",
                  "PV_PV1_total.csv","PV_PV2_total.csv","PV_PV3_total.csv","PV_PV4_total.csv",
                  "PHOTOVOLTAIC_PANELS.csv","GRID.csv","Total_demand.csv"]:
        df = cea_data["files"].get(fname)
        if df is not None:
            # Filter to selected buildings if applicable
            if selected_buildings and "name" in df.columns:
                df = df[df["name"].isin(selected_buildings)]
            lines.append(f"### {fname}\n{df.shape[0]}x{df.shape[1]}\n{', '.join(df.columns)}\n{df.head(10).to_csv(index=False)}")
    # Inject PV simulation config for relevant skills
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
    api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "max_tokens": 1500,
                  "messages": [{"role": "system", "content": system_prompt}] + messages},
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ API error: {e}"

def build_system_prompt(skill_md, cea_summary, output_mode, scale, selected_buildings=None):
    building_context = ""
    if selected_buildings:
        building_context = f"\nFocus your analysis specifically on: {', '.join(selected_buildings)}."
    return f"""You are a BIPV expert helping architects interpret CEA4 simulation results.
Output mode: {output_mode} | Scale: {scale}{building_context}

## Skill specification
{skill_md}

## CEA data
{cea_summary}

Follow the skill spec for the chosen output mode and scale. Use actual numbers from the data. Plain language for a design presentation. If a file is missing, say which CEA simulation needs to be run."""

def render_parameter_check(threshold_result, skill_id):
    """Render parameter check contextually for the selected skill."""
    if not threshold_result or threshold_result.get("error"):
        return

    simulations = SKILL_SIMULATION_MAP.get(skill_id, None)

    # No parameter check applicable
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

    # Only show parameter check for skills that use PV simulations
    if simulations is not None and "pv" not in simulations:
        st.markdown(
            '<div style="background:#f0fff4;border:1px solid #b2dfdb;border-radius:8px;'
            'padding:10px 14px;font-size:12.5px;color:#2e7d52;margin-bottom:12px;">'
            '✓ All parameter inputs look correct for this analysis.</div>',
            unsafe_allow_html=True
        )
        return

    # Detect which PV types were actually run (presence of PV_PVx_total.csv)
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

    # Use the highest threshold (most conservative — only carbon-viable surfaces included)
    max_ptype = max(type_thresholds, key=lambda p: type_thresholds[p])
    recommended = type_thresholds[max_ptype]
    driving_panel = PV_PANEL_TYPES.get(max_ptype, {})

    # Simulation label
    if len(run_pv_types) == 1:
        sim_label = f"Renewable Energy Potential Assessment<br>→ Photovoltaic ({run_pv_types[0]}: {PV_PANEL_TYPES.get(run_pv_types[0], {}).get('description', '')})"
    else:
        types_str = ", ".join([f"{p} ({PV_PANEL_TYPES.get(p,{}).get('description','')})" for p in run_pv_types])
        sim_label = f"Renewable Energy Potential Assessment<br>→ Photovoltaic ({types_str})"

    # Info text — show raw calculated value(s) and capped recommendation
    if len(run_pv_types) == 1:
        raw = int(type_thresholds_uncapped.get(run_pv_types[0], recommended))
        cap = int(recommended)
        panel_name = PV_PANEL_TYPES.get(run_pv_types[0], {}).get("description", "")
        if raw == cap:
            info_text = (
                f'For <b>{city}, {country}</b> (grid: {em_grid} kgCO&#x2082;/kWh), '
                f'the calculated threshold for {run_pv_types[0]} ({panel_name}) '
                f'is <b>{raw} kWh/m&#x00B2;/year</b>.'
            )
        else:
            info_text = (
                f'For <b>{city}, {country}</b> (grid: {em_grid} kgCO&#x2082;/kWh), '
                f'the formula gives {raw} kWh/m&#x00B2;/year for {run_pv_types[0]} ({panel_name}), '
                f'capped to a practical maximum of <b>{cap} kWh/m&#x00B2;/year</b>.'
            )
    else:
        per_panel_str = " &bull; ".join([
            f'{p}: {int(type_thresholds_uncapped.get(p, type_thresholds[p]))} kWh/m&#x00B2;/yr'
            for p in run_pv_types
        ])
        info_text = (
            f'For <b>{city}, {country}</b> (grid: {em_grid} kgCO&#x2082;/kWh), '
            f'the calculated thresholds are: {per_panel_str}. '
            f'Since CEA uses one threshold for all panel types, set it to '
            f'the most conservative value (carbon-viable surfaces only): <b>{int(recommended)} kWh/m&#x00B2;/year</b> '
            f'({max_ptype} — {driving_panel.get("description", "")}, highest embodied carbon).'
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
        # Status-driven styling: unverifiable=blue, wrong=red, correct=green
        status = "unverifiable"  # threshold cannot be read from the zip
        tooltip = "Cannot verify — check this value in CEA"
        if status == "wrong":
            bg, border = "#fff0f0", "#ffcccc"
        elif status == "correct":
            bg, border = "#f0fff4", "#b2dfdb"
        else:  # unverifiable
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
                f'Research on Zurich specifically found that a 10-year carbon payback '
                f'is not achievable for any panel type given its very clean grid. '
                f'Only CdTe panels get close (~18.5 years at best). '
                f'CEA\'s default of 800 kWh/m&sup2;/year was set for carbon-intensive grids '
                f'like Southeast Asia and is often too low for Europe.'
                f'{panel_section}'
                f'<br><span style="font-size:11px;color:#aaa;margin-top:6px;display:block;font-style:italic;">'
                f'Happle et al. (2019). J. Phys.: Conf. Ser. 1343, 012077. &bull; '
                f'Galimshina et al. (2024). Renew. Energy 236, 121404. &bull; '
                f'McCarty et al. (2025a). RSER 211, 115326. &bull; '
                f'McCarty et al. (2025b). J. Phys.: Conf. Ser. 3140, 032006.</span>'
                f'</div>',
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
              ("reasoning_open", False), ("reasoning_threshold", False)]:
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
                    cea_data["files"]["weather_header"], cea_default=800
                )
            st.rerun()

# ── Analysis screen ────────────────────────────────────────────────────────────
else:


    # ── Tree section (full width) ──────────────────────────────────────────────
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
                    st.rerun()

        # Building / Cluster selector
        if st.session_state.tree_scale in ["Building", "Cluster"]:
            building_names = get_building_names(st.session_state.cea_data)
            if building_names:
                st.markdown("")
                if st.session_state.tree_scale == "Building":
                    st.markdown("**Select building**")
                    chosen = st.selectbox(
                        "Building",
                        building_names,
                        index=building_names.index(st.session_state.selected_building)
                        if st.session_state.selected_building in building_names else 0,
                        label_visibility="collapsed",
                        key="building_selector"
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
                        "Buildings",
                        building_names,
                        default=st.session_state.selected_cluster,
                        label_visibility="collapsed",
                        key="cluster_selector"
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
                        st.session_state.tree_mode = None
                        st.session_state.analysis_ran = False
                        if not node["children"]:
                            st.session_state.skill_id = node["id"]
                            st.session_state.skill_name = topic
                        st.rerun()

        # Step 4: Analysis (if subtopics exist)
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
                            st.session_state.tree_mode = None
                            st.session_state.analysis_ran = False
                            st.session_state.skill_id = child_node["id"]
                            st.session_state.skill_name = child
                            st.rerun()

        # Step 5: Output mode
        skill_ready = st.session_state.skill_id and (
            not TREE.get(st.session_state.tree_goal, {}).get(
                st.session_state.tree_sub or "", {}).get("children") or
            st.session_state.tree_subsub
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
                        st.rerun()

        # Run button
        if st.session_state.tree_mode and st.session_state.skill_id and not st.session_state.analysis_ran:
            # Validate building/cluster selection
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
                # Step back one level
                if st.session_state.tree_mode:
                    st.session_state.tree_mode = None
                    st.session_state.analysis_ran = False
                elif st.session_state.tree_subsub:
                    st.session_state.tree_subsub = None
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
                st.rerun()
        with col_b:
            if st.button("↺ Start over"):
                for k in ["tree_scale","tree_goal","tree_sub","tree_subsub",
                          "tree_mode","skill_id","skill_name","analysis_ran",
                          "selected_building","selected_cluster"]:
                    st.session_state[k] = None if k != "selected_cluster" else []
                st.session_state.chat_history = []
                st.rerun()
        with col_c:
            if st.button("↩ New project"):
                for k in ["cea_data","tree_scale","tree_goal","tree_sub","tree_subsub",
                          "tree_mode","skill_id","skill_name","analysis_ran",
                          "threshold_result","param_check_hidden",
                          "selected_building","selected_cluster"]:
                    st.session_state[k] = None if k != "selected_cluster" else []
                st.session_state.chat_history = []
                st.rerun()

    # ── Analysis section (full width, below tree) ──────────────────────────────
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
            system_prompt = build_system_prompt(
                skill_md, cea_summary,
                st.session_state.tree_mode,
                scale,
                selected_buildings=selected_buildings
            )
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
                st.markdown(f'<div class="bubble-ai">{msg["content"]}</div><div class="clearfix"></div>',
                           unsafe_allow_html=True)

        if st.session_state.chat_history:
            st.markdown("---")
            followup = st.text_input("Ask a follow-up…", key="fu",
                                    placeholder="e.g. Which building has the best south facade?")
            if st.button("Send") and followup.strip():
                scale = st.session_state.tree_scale
                selected_buildings = None
                if scale == "Building" and st.session_state.selected_building:
                    selected_buildings = [st.session_state.selected_building]
                elif scale == "Cluster" and st.session_state.selected_cluster:
                    selected_buildings = st.session_state.selected_cluster

                skill_md = load_skill_md(st.session_state.skill_id or "")
                cea_summary = build_data_summary(
                    st.session_state.cea_data,
                    selected_buildings=selected_buildings,
                    scale=scale or ""
                )
                system_prompt = build_system_prompt(
                    skill_md, cea_summary,
                    st.session_state.tree_mode or "",
                    scale or "",
                    selected_buildings=selected_buildings
                )
                st.session_state.chat_history.append({"role": "user", "content": followup})
                with st.spinner("Thinking…"):
                    response = call_llm(system_prompt, st.session_state.chat_history)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
