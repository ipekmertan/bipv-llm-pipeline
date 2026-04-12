import streamlit as st
import zipfile
import json
import os
import io
import tempfile
import pandas as pd
from pathlib import Path
import requests

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BIPV Analyst",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'DM Serif Display', serif; }
[data-testid="stSidebar"] { background: #0f1117; border-right: 1px solid #1e2535; }
[data-testid="stSidebar"] * { color: #e8e8e8 !important; }
.main { background: #f8f7f4; }
.bubble-user {
    background: #2d3142; color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 0.8rem 1.1rem; margin: 0.5rem 0 0.5rem auto;
    max-width: 75%; width: fit-content; float: right; clear: both;
}
.bubble-ai {
    background: white; border: 1px solid #e8e4dc;
    border-radius: 18px 18px 18px 4px;
    padding: 0.8rem 1.1rem; margin: 0.5rem auto 0.5rem 0;
    max-width: 85%; width: fit-content; float: left; clear: both; line-height: 1.65;
}
.clearfix { clear: both; }
.section-label {
    font-size: 0.7rem; font-weight: 500; letter-spacing: 0.12em;
    text-transform: uppercase; color: #9a9a9a; margin: 1.2rem 0 0.4rem 0;
}
.info-box {
    background: #fffbf0; border-left: 3px solid #c8a96e;
    padding: 0.8rem 1rem; border-radius: 0 8px 8px 0;
    margin: 1rem 0; font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)


# ── Constants ──────────────────────────────────────────────────────────────────
SKILLS_INDEX_PATH = Path(__file__).parent / "configuration" / "skills-index.json"
SKILLS_DIR = Path(__file__).parent / "skills"


# ── Helpers ────────────────────────────────────────────────────────────────────

@st.cache_data
def load_skills_index():
    with open(SKILLS_INDEX_PATH) as f:
        return json.load(f)["skills"]


def load_skill_md(skill_id: str) -> str:
    for folder in SKILLS_DIR.iterdir():
        if folder.name.strip() == skill_id:
            md_path = folder / "SKILL.md"
            if md_path.exists():
                return md_path.read_text()
    return ""


def extract_cea_zip(uploaded_file) -> dict:
    """
    Extract a CEA project zip and map files using the real CEA folder structure:
    - export/results/summary-YYYYMMDD-HHMMSS/  ← irradiation + demand summaries (use most recent)
    - outputs/data/potentials/solar/            ← PV yield totals
    - outputs/data/demand/                      ← hourly demand per building
    - inputs/database/COMPONENTS/...            ← panel database (PHOTOVOLTAIC_PANELS.csv, GRID.csv)
    - inputs/weather/weather.epw                ← location context
    """
    result = {
        "project_name": None,
        "scenario_name": None,
        "latest_export": None,      # name of the most recent summary folder
        "files": {},                # logical_key → DataFrame
        "available_simulations": [], # which simulation types were found
        "errors": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:
            zf.extractall(tmpdir)

        root = Path(tmpdir)

        # Find the scenario root (first subfolder)
        top = [d for d in root.iterdir() if d.is_dir()]
        if not top:
            result["errors"].append("Could not find project folder inside zip.")
            return result
        scenario = top[0]
        result["project_name"] = scenario.name

        # ── 1. Most recent export summary ──────────────────────────────────────
        export_dir = scenario / "export" / "results"
        if export_dir.exists():
            summaries = sorted(
                [d for d in export_dir.iterdir() if d.is_dir()],
                reverse=True
            )
            if summaries:
                latest = summaries[0]
                result["latest_export"] = latest.name

                # Solar irradiation files
                irr_dir = latest / "solar_irradiation"
                for fname in [
                    "solar_irradiation_annually.csv",
                    "solar_irradiation_annually_buildings.csv",
                    "solar_irradiation_seasonally.csv",
                    "solar_irradiation_seasonally_buildings.csv",
                    "solar_irradiation_daily.csv",
                    "solar_irradiation_hourly.csv",
                    "solar_irradiation_monthly.csv",
                    "solar_irradiation_monthly_buildings.csv",
                ]:
                    fpath = irr_dir / fname
                    if fpath.exists():
                        try:
                            result["files"][fname] = pd.read_csv(fpath)
                        except Exception as e:
                            result["errors"].append(f"{fname}: {e}")

                # Demand summary files
                demand_dir = latest / "demand"
                for fname in [
                    "demand_annually.csv",
                    "demand_annually_buildings.csv",
                    "demand_seasonally.csv",
                    "demand_daily.csv",
                ]:
                    fpath = demand_dir / fname
                    if fpath.exists():
                        try:
                            result["files"][fname] = pd.read_csv(fpath)
                        except Exception as e:
                            result["errors"].append(f"{fname}: {e}")

        # ── 2. PV yield totals ─────────────────────────────────────────────────
        pv_dir = scenario / "outputs" / "data" / "potentials" / "solar"
        if pv_dir.exists():
            for fpath in sorted(pv_dir.glob("PV_*_total*.csv")):
                try:
                    result["files"][fpath.name] = pd.read_csv(fpath)
                except Exception as e:
                    result["errors"].append(f"{fpath.name}: {e}")
            for fpath in sorted(pv_dir.glob("PVT_*_total*.csv")):
                try:
                    result["files"][fpath.name] = pd.read_csv(fpath)
                except Exception as e:
                    result["errors"].append(f"{fpath.name}: {e}")

        # ── 3. Total demand (hourly per building) ──────────────────────────────
        demand_raw = scenario / "outputs" / "data" / "demand"
        for fname in ["Total_demand.csv", "Total_demand_hourly.csv"]:
            fpath = demand_raw / fname
            if fpath.exists():
                try:
                    result["files"][fname] = pd.read_csv(fpath)
                except Exception as e:
                    result["errors"].append(f"{fname}: {e}")

        # ── 4. Panel database & grid data ─────────────────────────────────────
        db_conversion = scenario / "inputs" / "database" / "COMPONENTS" / "CONVERSION"
        for fname in ["PHOTOVOLTAIC_PANELS.csv", "PHOTOVOLTAIC_THERMAL_PANELS.csv"]:
            fpath = db_conversion / fname
            if fpath.exists():
                try:
                    result["files"][fname] = pd.read_csv(fpath)
                except Exception as e:
                    result["errors"].append(f"{fname}: {e}")

        grid_path = scenario / "inputs" / "database" / "COMPONENTS" / "FEEDSTOCKS" / "FEEDSTOCKS_LIBRARY" / "GRID.csv"
        if grid_path.exists():
            try:
                result["files"]["GRID.csv"] = pd.read_csv(grid_path)
            except Exception as e:
                result["errors"].append(f"GRID.csv: {e}")

        # ── 5. Weather file (location context) ────────────────────────────────
        epw_path = scenario / "inputs" / "weather" / "weather.epw"
        if epw_path.exists():
            # Read first line of EPW for city/location
            try:
                with open(epw_path, "r", errors="ignore") as f:
                    first_line = f.readline()
                result["files"]["weather_header"] = first_line.strip()
            except Exception as e:
                result["errors"].append(f"weather.epw: {e}")

        # ── Detect which simulations are available ─────────────────────────────
        sims = []
        if "solar_irradiation_annually.csv" in result["files"]:
            sims.append("Solar Irradiation")
        if any(k.startswith("PV_") for k in result["files"]):
            sims.append("PV Yield")
        if any(k.startswith("PVT_") for k in result["files"]):
            sims.append("PVT Yield")
        if "demand_annually.csv" in result["files"] or "Total_demand.csv" in result["files"]:
            sims.append("Demand")
        result["available_simulations"] = sims

    return result


def build_data_summary(cea_data: dict) -> str:
    """Compact text summary of available CEA data for the LLM."""
    lines = []

    # Location
    if "weather_header" in cea_data["files"]:
        lines.append(f"## Location\n{cea_data['files']['weather_header']}\n")

    lines.append(f"## Available simulations\n{', '.join(cea_data['available_simulations'])}\n")

    # Key files — send head rows only to keep prompt size manageable
    priority_files = [
        "solar_irradiation_annually.csv",
        "solar_irradiation_annually_buildings.csv",
        "solar_irradiation_seasonally.csv",
        "solar_irradiation_daily.csv",
        "demand_annually.csv",
        "demand_annually_buildings.csv",
        "PV_PV1_total.csv",
        "PV_PV1_total_buildings.csv",
        "PV_PV2_total.csv",
        "PV_PV3_total.csv",
        "PV_PV4_total.csv",
        "PHOTOVOLTAIC_PANELS.csv",
        "GRID.csv",
        "Total_demand.csv",
    ]

    lines.append("## Simulation data\n")
    for fname in priority_files:
        df = cea_data["files"].get(fname)
        if df is not None:
            lines.append(f"### {fname}")
            lines.append(f"Shape: {df.shape[0]} rows × {df.shape[1]} cols")
            lines.append(f"Columns: {', '.join(df.columns.tolist())}")
            lines.append(df.head(5).to_csv(index=False))
            lines.append("")

    return "\n".join(lines)

def call_claude(system_prompt: str, messages: list) -> str:
    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o",
        "max_tokens": 1500,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
    }
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ API error: {e}"


def build_system_prompt(skill_md: str, cea_summary: str, output_mode: str) -> str:
    return f"""You are a BIPV (Building-Integrated Photovoltaics) expert assistant helping architects
interpret simulation results from the City Energy Analyst (CEA4).

You have been given:
1. A skill specification defining exactly what analysis to perform and how to present it
2. The architect's actual CEA simulation data
3. The architect's chosen output mode: **{output_mode}**

## Skill specification
{skill_md}

## CEA simulation data
{cea_summary}

## Instructions
- Follow the skill specification exactly for the chosen output mode
- Write in plain language an architect can use in a design presentation
- Be specific — use actual numbers from the data
- If a required file is missing, say clearly which simulation needs to be run in CEA to generate it
- Do not invent numbers — only use what is in the data provided
"""


# ── Session state ──────────────────────────────────────────────────────────────
if "cea_data" not in st.session_state:
    st.session_state.cea_data = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_skill" not in st.session_state:
    st.session_state.selected_skill = None
if "output_mode" not in st.session_state:
    st.session_state.output_mode = "Key takeaway"


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ☀️ BIPV Analyst")
    st.markdown("*Post-simulation analysis for architects*")
    st.markdown("---")

    if st.session_state.cea_data:
        st.markdown('<p class="section-label">Project loaded</p>', unsafe_allow_html=True)
        sims = st.session_state.cea_data["available_simulations"]
        for sim in sims:
            st.markdown(f"✓ {sim}")

        if st.button("↩ Upload new project", use_container_width=True):
            st.session_state.cea_data = None
            st.session_state.chat_history = []
            st.session_state.selected_skill = None
            st.rerun()

        st.markdown("---")
        st.markdown('<p class="section-label">Output mode</p>', unsafe_allow_html=True)
        st.session_state.output_mode = st.radio(
            "How do you want the answer?",
            ["Key takeaway", "Explain the numbers", "Design implication"],
            label_visibility="collapsed",
        )
    else:
        st.markdown("Upload your CEA project zip to begin.")


# ── Main ───────────────────────────────────────────────────────────────────────
skills = load_skills_index()

if st.session_state.cea_data is None:
    st.markdown("# BIPV Analyst")
    st.markdown("Upload your CEA4 project folder (zipped) to begin analysis.")

    st.markdown("""
    <div class="info-box">
    <strong>How to export from CEA4:</strong> Go to your CEA project folder on disk,
    select the entire folder (named after your scenario, e.g. <code>baseline</code>),
    compress it to a <code>.zip</code> file, and upload it here.
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Drop your CEA project zip here",
        type=["zip"],
        label_visibility="collapsed",
    )

    if uploaded:
        with st.spinner("Reading project…"):
            cea_data = extract_cea_zip(uploaded)

        if not cea_data["files"]:
            st.error("No simulation files found. Make sure you're uploading the full CEA scenario folder.")
            if cea_data["errors"]:
                st.code("\n".join(cea_data["errors"]))
        else:
            st.session_state.cea_data = cea_data
            st.rerun()

    st.markdown("---")
    st.markdown("### What this tool analyses")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("**🔍 Site Potential**\nSurface irradiation, envelope suitability, seasonal & daily patterns")
    with col2:
        st.markdown("**⚡ Performance**\nEnergy generation, self-sufficiency, demand vs supply")
    with col3:
        st.markdown("**🌿 Carbon & Cost**\nPayback periods, embodied carbon, LCOE by panel type")
    with col4:
        st.markdown("**🏗️ Design Optimisation**\nPanel trade-offs, surface prioritisation, integration")

else:
    col_tree, col_chat = st.columns([1, 2], gap="large")

    with col_tree:
        st.markdown("### Choose an analysis")

        branches = {}
        for skill in skills:
            top = skill["position_in_tree"][0]
            branches.setdefault(top, []).append(skill)

        for branch, branch_skills in branches.items():
            st.markdown(f'<p class="section-label">{branch}</p>', unsafe_allow_html=True)
            for skill in branch_skills:
                label = " → ".join(skill["position_in_tree"][1:]) or skill["display_name"]
                if st.button(label, key=skill["id"], use_container_width=True, help=skill.get("tooltip", "")):
                    st.session_state.selected_skill = skill
                    st.session_state.chat_history = []
                    st.rerun()

    with col_chat:
        st.markdown("### Analysis")

        if st.session_state.selected_skill:
            skill = st.session_state.selected_skill
            st.markdown(f"**{skill['display_name']}**")
            st.markdown(f"*{skill.get('tooltip', '')}*")
            st.markdown(f"Output mode: **{st.session_state.output_mode}**")

            if st.button("▶ Run analysis", type="primary"):
                skill_md = load_skill_md(skill["id"])
                cea_summary = build_data_summary(st.session_state.cea_data)
                system_prompt = build_system_prompt(skill_md, cea_summary, st.session_state.output_mode)

                user_msg = (
                    f"Run the **{skill['display_name']}** analysis in **{st.session_state.output_mode}** mode. "
                    f"Use only the data provided. Be specific with numbers from the data."
                )
                st.session_state.chat_history.append({"role": "user", "content": user_msg})

                with st.spinner("Analysing…"):
                    response = call_claude(system_prompt, st.session_state.chat_history)

                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

            st.markdown("---")
        else:
            st.markdown(
                '<div class="info-box">← Select an analysis from the left to begin.</div>',
                unsafe_allow_html=True,
            )

        # Chat history display
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="bubble-user">{msg["content"]}</div><div class="clearfix"></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="bubble-ai">{msg["content"]}</div><div class="clearfix"></div>', unsafe_allow_html=True)

        # Follow-up input
        if st.session_state.chat_history:
            st.markdown("---")
            followup = st.text_input(
                "Ask a follow-up question…",
                key="followup_input",
                placeholder="e.g. Which building has the best south facade potential?",
            )
            if st.button("Send", key="send_followup") and followup.strip():
                skill = st.session_state.selected_skill
                skill_md = load_skill_md(skill["id"]) if skill else ""
                cea_summary = build_data_summary(st.session_state.cea_data)
                system_prompt = build_system_prompt(skill_md, cea_summary, st.session_state.output_mode)

                st.session_state.chat_history.append({"role": "user", "content": followup})

                with st.spinner("Thinking…"):
                    response = call_claude(system_prompt, st.session_state.chat_history)

                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()
