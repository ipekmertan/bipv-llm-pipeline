"""
BIPV Analyst — Streamlit web app
Reads a CEA project zip, extracts grid emissions + self-consumption automatically,
fetches ACACIA LCA curves, and presents threshold analysis grounded in
McCarty et al. 2025 and Happle et al. 2019.
"""

import io
import os
import json
import zipfile
import tempfile
import requests
import numpy as np
import pandas as pd
import streamlit as st


# ── Config ──────────────────────────────────────────────────────────────────

ACACIA_CURVE_URL = "https://acacia.arch.ethz.ch/static/data/static_curve_data.json"
SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
SKILLS_INDEX = os.path.join(os.path.dirname(__file__), "configuration", "skills-index.json")

# Grid emissions conversion: CEA stores kgCO2/MJ in GRID.csv
# 1 kWh = 3.6 MJ → multiply by 3.6 to get kgCO2/kWh
MJ_TO_KWH = 3.6

# McCarty 2025 — threshold table (location × technology × metric)
# Values in kWh/m²/year
MCCARTY_THRESHOLDS = {
    "singapore": {
        "grid_kgco2_kwh": 0.566,
        "csi":  {"yspec": 524, "carbon_intensity": 137, "cpp_10yr": 325},
        "cdte": {"yspec": 500, "carbon_intensity": 65,  "cpp_10yr": 155},
        "opv":  {"yspec": 506, "carbon_intensity": 116, "cpp_10yr": 274},
    },
    "hamburg": {
        "grid_kgco2_kwh": 0.298,
        "csi":  {"yspec": 522, "carbon_intensity": 227, "cpp_10yr": 730},
        "cdte": {"yspec": 503, "carbon_intensity": 110, "cpp_10yr": 351},
        "opv":  {"yspec": 500, "carbon_intensity": 199, "cpp_10yr": 638},
    },
    "zurich": {
        "grid_kgco2_kwh": 0.046,
        "csi":  {"yspec": 500, "carbon_intensity": 1405, "cpp_10yr": 4512},
        "cdte": {"yspec": 504, "carbon_intensity": 678,  "cpp_10yr": 2184},
        "opv":  {"yspec": 500, "carbon_intensity": 1219, "cpp_10yr": 3930},
    },
}

# CEA panel database (McCarty IDP lecture + CEA PHOTOVOLTAIC_PANELS.csv)
PANEL_DB = {
    "PV1": {"tech": "cSi",  "label": "Crystalline Silicon",   "efficiency": 0.185, "embodied_kgco2_m2": 255.8, "cost_roof": 254.72, "cost_facade": 345.72, "acacia_key": "monocrystalline"},
    "PV2": {"tech": "mcSi", "label": "Monocrystalline Silicon","efficiency": 0.175, "embodied_kgco2_m2": 191.2, "cost_roof": 238.58, "cost_facade": 329.58, "acacia_key": "monocrystalline"},
    "PV3": {"tech": "CdTe", "label": "Cadmium-Telluride",      "efficiency": 0.176, "embodied_kgco2_m2": 47.6,  "cost_roof": 239.54, "cost_facade": 330.54, "acacia_key": "cdte"},
    "PV4": {"tech": "CIGS", "label": "CIGS",                   "efficiency": 0.099, "embodied_kgco2_m2": 75.9,  "cost_roof": 265.06, "cost_facade": 356.06, "acacia_key": "cigs"},
}


# ── CEA zip extraction ───────────────────────────────────────────────────────

def extract_cea_zip(uploaded_file) -> dict:
    """
    Extract a CEA project zip.
    Returns a dict with:
      - files: {filename → DataFrame}
      - raw_paths: all paths found
      - errors: any read errors
      - project_name: top-level folder name
    """
    result = {"files": {}, "raw_paths": [], "errors": [], "project_name": None}

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:
            zf.extractall(tmpdir)

        for root, dirs, files in os.walk(tmpdir):
            for fname in files:
                full = os.path.join(root, fname)
                rel  = os.path.relpath(full, tmpdir)
                result["raw_paths"].append(rel)
                if fname.endswith(".csv"):
                    try:
                        result["files"][fname] = pd.read_csv(full)
                    except Exception as e:
                        result["errors"].append(f"{fname}: {e}")

        top = [d for d in os.listdir(tmpdir) if os.path.isdir(os.path.join(tmpdir, d))]
        if top:
            result["project_name"] = top[0]

    return result


def extract_grid_emissions(cea_data: dict) -> float | None:
    """
    Read grid carbon intensity from GRID.csv.
    CEA stores it as kgCO2/MJ — convert to kgCO2/kWh (* 3.6).
    Returns kgCO2/kWh or None if not found.
    """
    df = cea_data["files"].get("GRID.csv")
    if df is None:
        return None
    # Column name varies slightly across CEA versions
    for col in ["GHG_kgCO2MJ", "CO2", "ghg_kgCO2MJ", "co2"]:
        if col in df.columns:
            val = df[col].iloc[0]
            return round(float(val) * MJ_TO_KWH, 4)
    # Fallback: look for any column containing "CO2" or "ghg"
    co2_cols = [c for c in df.columns if "co2" in c.lower() or "ghg" in c.lower()]
    if co2_cols:
        val = df[co2_cols[0]].iloc[0]
        return round(float(val) * MJ_TO_KWH, 4)
    return None


def detect_pv_panel_types(cea_data: dict) -> list[str]:
    """
    Detect which PV panel types were simulated.
    Looks for files like PV_PV1_total.csv, PV_PV2_total_buildings.csv etc.
    Returns list of panel codes e.g. ['PV1', 'PV3']
    """
    panels = set()
    for fname in cea_data["files"]:
        for pv in ["PV1", "PV2", "PV3", "PV4"]:
            if pv in fname and fname.startswith("PV_"):
                panels.add(pv)
    return sorted(list(panels))


def calculate_self_consumption(cea_data: dict, panel_type: str) -> float | None:
    """
    Calculate self-consumption ratio from PV generation and demand files.
    self_consumption = sum(min(pv_gen_h, demand_h)) / sum(pv_gen_h)

    Uses hourly data if available, falls back to annual totals ratio.
    Returns fraction (0–1) or None if data unavailable.
    """
    # Try hourly PV file
    pv_fname = f"PV_{panel_type}_total.csv"
    pv_df = cea_data["files"].get(pv_fname)

    if pv_df is None:
        return None

    # Find generation column
    gen_col = next((c for c in pv_df.columns if "E_PV_gen" in c or "E_PV" in c), None)
    if gen_col is None:
        return None

    total_gen = pv_df[gen_col].sum()
    if total_gen == 0:
        return None

    # Try to match with demand file(s)
    # Aggregate all B{id}.csv demand files
    demand_dfs = [df for fname, df in cea_data["files"].items()
                  if fname.startswith("B") and fname.endswith(".csv") and len(fname) <= 10]

    if demand_dfs:
        # Sum all building demands hour by hour
        demand_series = sum(df["E_sys_kWh"].values for df in demand_dfs
                            if "E_sys_kWh" in df.columns)
        if hasattr(demand_series, "__len__") and len(demand_series) == len(pv_df):
            gen = pv_df[gen_col].values
            self_consumed = np.minimum(gen, demand_series).sum()
            return round(float(self_consumed / total_gen), 3)

    # Fallback: use annual buildings file if available
    bldg_fname = f"PV_{panel_type}_total_buildings.csv"
    bldg_df = cea_data["files"].get(bldg_fname)
    if bldg_df is not None:
        sc_col = next((c for c in bldg_df.columns if "self_consumption" in c.lower() or "SC" in c), None)
        if sc_col:
            return round(float(bldg_df[sc_col].mean()), 3)

    # Final fallback: assume 0.5 and flag it
    return None


# ── ACACIA curve lookup ──────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_acacia_curves() -> dict | None:
    """Fetch ACACIA static curve data. Cached for 1 hour."""
    try:
        r = requests.get(ACACIA_CURVE_URL, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def nearest_key(obj: dict, value: float) -> str:
    keys = sorted([float(k) for k in obj.keys()])
    nearest = min(keys, key=lambda k: abs(k - value))
    return f"{nearest:.2f}"


def get_carbon_threshold(
    acacia_data: dict,
    panel_type: str,          # CEA panel code e.g. 'PV3'
    grid_emissions: float,    # kgCO2/kWh
    self_consumption: float,  # fraction
) -> dict:
    """
    Look up the carbon break-even irradiance threshold from ACACIA curves.
    Returns dict with threshold_exact, threshold_cea, and metadata.
    """
    panel_info = PANEL_DB.get(panel_type, PANEL_DB["PV3"])
    acacia_key = panel_info["acacia_key"]

    # Match to available ACACIA panel key
    panel_key = next(
        (k for k in acacia_data if k.lower().replace(" ", "") == acacia_key.replace(" ", "")),
        list(acacia_data.keys())[0]
    )

    grid_key = nearest_key(acacia_data[panel_key], grid_emissions)
    sc_key   = nearest_key(acacia_data[panel_key][grid_key], self_consumption)
    series   = acacia_data[panel_key][grid_key][sc_key]

    irr = np.array(series["Irradiance"])
    imp = np.array(series["Impact"])

    # Find zero crossing (carbon break-even)
    threshold = None
    for i in range(1, len(imp)):
        if imp[i - 1] > 0 and imp[i] <= 0:
            x0, x1 = irr[i - 1], irr[i]
            y0, y1 = imp[i - 1], imp[i]
            threshold = x0 + (0 - y0) * (x1 - x0) / (y1 - y0)
            break

    threshold_exact = round(threshold) if threshold else None
    threshold_cea   = round(threshold / 50) * 50 if threshold else None

    # McCarty Yspec reference: 500–525 kWh/m²/year regardless of location
    yspec_target = 500

    # Contextualise: which McCarty location is closest in grid emissions?
    closest_location = min(
        MCCARTY_THRESHOLDS.items(),
        key=lambda kv: abs(kv[1]["grid_kgco2_kwh"] - grid_emissions)
    )
    loc_name, loc_data = closest_location
    tech_key = "cdte" if "cdte" in acacia_key else ("opv" if "organic" in acacia_key else "csi")
    mccarty_cpp = loc_data.get(tech_key, {}).get("cpp_10yr")
    mccarty_ci  = loc_data.get(tech_key, {}).get("carbon_intensity")

    return {
        "panel_type": panel_type,
        "panel_label": panel_info["label"],
        "acacia_key_used": panel_key,
        "grid_key_used": float(grid_key),
        "sc_key_used": float(sc_key),
        "threshold_exact": threshold_exact,
        "threshold_cea": threshold_cea,
        "yspec_target": yspec_target,
        "irradiance": irr.tolist(),
        "impact": imp.tolist(),
        "mccarty_closest_location": loc_name,
        "mccarty_cpp_10yr": mccarty_cpp,
        "mccarty_carbon_intensity": mccarty_ci,
        "embodied_kgco2_m2": panel_info["embodied_kgco2_m2"],
    }


# ── Skill loading ────────────────────────────────────────────────────────────

@st.cache_data
def load_skills_index() -> dict:
    if os.path.exists(SKILLS_INDEX):
        with open(SKILLS_INDEX) as f:
            return json.load(f)
    return {}


def load_skill_prompt(skill_id: str) -> str:
    """Load SKILL.md content for a given skill id."""
    for folder in os.listdir(SKILLS_DIR):
        if folder.strip() == skill_id:
            md_path = os.path.join(SKILLS_DIR, folder, "SKILL.md")
            if os.path.exists(md_path):
                with open(md_path) as f:
                    return f.read()
    return ""


# ── Claude API ───────────────────────────────────────────────────────────────

def call_claude(system_prompt: str, user_message: str) -> str:
    """Call LLM API."""
    api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "max_tokens": 1500,
                  "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_message}]},
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ API error: {e}"


def build_threshold_context(threshold_result: dict, grid_emissions: float, self_consumption: float) -> str:
    """Build the threshold context block to inject into skill prompts."""
    return f"""
## BIPV Threshold Analysis (from ACACIA + McCarty et al. 2025)

Panel type: {threshold_result['panel_label']} ({threshold_result['panel_type']})
Grid carbon intensity (from GRID.csv): {grid_emissions:.3f} kgCO₂/kWh
Self-consumption ratio (from PV CSVs): {self_consumption:.2f}

Carbon break-even threshold (ACACIA): {threshold_result['threshold_exact']} kWh/m²/year
Recommended CEA input value (rounded to nearest 50): {threshold_result['threshold_cea']} kWh/m²/year

McCarty et al. 2025 reference thresholds (closest location: {threshold_result['mccarty_closest_location']}):
- Specific yield (Yspec) target: {threshold_result['yspec_target']} kWh/m²/year (consistent across all locations)
- Carbon intensity threshold: {threshold_result['mccarty_carbon_intensity']} kWh/m²/year
- Carbon payback period (10yr target): {threshold_result['mccarty_cpp_10yr']} kWh/m²/year

Note (McCarty 2025): Annual mean grid emissions may underestimate CPP threshold by up to 28%
in high-variability grid contexts. The ACACIA curve-derived threshold above uses the annual mean.

Panel embodied carbon: {threshold_result['embodied_kgco2_m2']} kgCO₂/m²

Source: ACACIA parametric BIPV LCA (ETH Zürich) · McCarty et al. 2025 · Happle et al. 2019
"""


# ── Streamlit UI ─────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="BIPV Analyst",
        page_icon="☀️",
        layout="wide",
    )

    st.title("BIPV Analyst")
    st.caption("Upload a CEA project zip to analyse building-integrated photovoltaic performance.")

    # ── Session state ──
    if "cea_data"   not in st.session_state: st.session_state.cea_data   = None
    if "grid_em"    not in st.session_state: st.session_state.grid_em    = None
    if "panel_types"not in st.session_state: st.session_state.panel_types= []
    if "sc_ratios"  not in st.session_state: st.session_state.sc_ratios  = {}
    if "thresholds" not in st.session_state: st.session_state.thresholds = {}
    if "messages"   not in st.session_state: st.session_state.messages   = []

    # ── Sidebar: upload + status ──
    with st.sidebar:
        st.header("Project")
        uploaded = st.file_uploader("Upload CEA project zip", type="zip")

        if uploaded:
            with st.spinner("Extracting zip..."):
                cea_data = extract_cea_zip(uploaded)
                st.session_state.cea_data = cea_data

            # Extract grid emissions
            grid_em = extract_grid_emissions(cea_data)
            st.session_state.grid_em = grid_em

            # Detect panel types
            panels = detect_pv_panel_types(cea_data)
            st.session_state.panel_types = panels

            # Calculate self-consumption per panel type
            for p in panels:
                sc = calculate_self_consumption(cea_data, p)
                st.session_state.sc_ratios[p] = sc if sc is not None else 0.50

            st.success(f"Loaded: {cea_data.get('project_name', 'CEA project')}")

            if grid_em:
                st.metric("Grid emissions", f"{grid_em:.3f} kgCO₂/kWh", help="From GRID.csv · kgCO₂/kWh")
            else:
                st.warning("GRID.csv not found — grid emissions unavailable")

            if panels:
                st.write("**Simulated panel types:**", ", ".join(panels))
                for p in panels:
                    sc = st.session_state.sc_ratios.get(p)
                    if sc:
                        st.write(f"  {p} self-consumption: {sc:.2f}")
                    else:
                        st.write(f"  {p} self-consumption: estimated 0.50")
            else:
                st.warning("No PV simulation results found in zip")

        # ── Threshold summary in sidebar ──
        if st.session_state.thresholds:
            st.divider()
            st.subheader("Thresholds")
            for p, t in st.session_state.thresholds.items():
                st.metric(
                    label=f"{p} ({t['panel_label']})",
                    value=f"{t['threshold_cea']} kWh/m²/yr",
                    help=f"Exact: {t['threshold_exact']} · CEA input (rounded to 50): {t['threshold_cea']}"
                )

    # ── Main area ──
    if st.session_state.cea_data is None:
        st.info("Upload a CEA project zip to get started.")
        return

    # ── Panel type selector + threshold computation ──
    panels = st.session_state.panel_types
    if not panels:
        st.warning("No PV simulation results detected in the uploaded zip.")
        return

    selected_panel = panels[0]
    if len(panels) > 1:
        selected_panel = st.selectbox(
            "Panel type (simulated in your project)",
            options=panels,
            format_func=lambda p: f"{p} — {PANEL_DB.get(p, {}).get('label', p)}"
        )

    # Compute threshold for selected panel if not already done
    acacia_data = fetch_acacia_curves()
    grid_em = st.session_state.grid_em
    sc = st.session_state.sc_ratios.get(selected_panel, 0.50)

    if acacia_data and grid_em and selected_panel not in st.session_state.thresholds:
        t = get_carbon_threshold(acacia_data, selected_panel, grid_em, sc)
        st.session_state.thresholds[selected_panel] = t

    threshold_result = st.session_state.thresholds.get(selected_panel)

    # ── Threshold display ──
    if threshold_result:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Carbon break-even", f"{threshold_result['threshold_exact']} kWh/m²/yr",
                    help="Irradiance where PV carbon intensity equals grid carbon intensity (ACACIA + Happle 2019)")
        col2.metric("CEA input value", f"{threshold_result['threshold_cea']} kWh/m²/yr",
                    help="Rounded to nearest 50 for use in CEA radiation threshold field")
        col3.metric("McCarty Yspec target", "500–525 kWh/m²/yr",
                    help="Consistent across all locations and technologies (McCarty et al. 2025)")
        col4.metric("Closest reference", threshold_result["mccarty_closest_location"].title(),
                    help=f"Grid emissions match: {threshold_result['grid_key_used']:.2f} kgCO₂/kWh")

        # McCarty CPP context
        if threshold_result["mccarty_cpp_10yr"]:
            st.caption(
                f"McCarty 2025 CPP threshold for 10-year carbon payback "
                f"({threshold_result['mccarty_closest_location'].title()}, {threshold_result['panel_label']}): "
                f"**{threshold_result['mccarty_cpp_10yr']} kWh/m²/yr** · "
                f"Annual mean grid data may underestimate CPP threshold by up to 28% in variable-grid contexts."
            )

    st.divider()

    # ── Decision tree ──
    st.subheader("What do you want to understand?")
    skills_index = load_skills_index()

    goal = st.selectbox("Goal", [
        "Site potential",
        "Impact & viability",
        "Optimise my design",
    ])

    # Sub-branch options per goal (abbreviated — full tree in skills-index.json)
    sub_options = {
        "Site potential": [
            "Solar availability — surface irradiation",
            "Solar availability — seasonal variation",
            "Contextual feasibility — shading analysis",
        ],
        "Impact & viability": [
            "Carbon impact — carbon payback",
            "Carbon impact — operational carbon footprint",
            "Economic viability — cost analysis",
            "Economic viability — investment payback",
        ],
        "Optimise my design": [
            "Panel type trade-off",
            "BIPV scenario comparison",
            "Demand vs supply match",
        ],
    }

    sub = st.selectbox("Focus", sub_options.get(goal, []))

    output_mode = st.radio(
        "Output style",
        ["Key takeaway", "Explain the numbers", "Design implication"],
        horizontal=True,
    )

    # ── Run analysis ──
    if st.button("Run analysis", type="primary"):
        # Find matching skill id from index
        skill_id = None
        for sid, meta in skills_index.items():
            label = meta.get("label", "").lower()
            if any(word in label for word in sub.lower().split("—")[-1].strip().split()):
                skill_id = sid
                break

        skill_prompt = load_skill_prompt(skill_id) if skill_id else ""

        # Build data summary
        data_lines = []
        for fname, df in st.session_state.cea_data["files"].items():
            if df is not None and any(kw in fname for kw in ["PV_", "solar", "emission", "demand"]):
                data_lines.append(f"### {fname}\nColumns: {', '.join(df.columns)}\n{df.head(3).to_csv(index=False)}")
        data_summary = "\n\n".join(data_lines[:6])  # cap at 6 files to stay within context

        # Build threshold context
        threshold_ctx = ""
        if threshold_result:
            threshold_ctx = build_threshold_context(threshold_result, grid_em, sc)

        system = f"""You are a BIPV analysis assistant embedded in a tool used by architects.
Your job is to interpret CEA simulation results and give clear, design-ready insights.

{skill_prompt}

{threshold_ctx}

Output mode requested: {output_mode}
- Key takeaway: 2–3 sentences max, one headline number, one design implication
- Explain the numbers: walk through each metric clearly, explain what it means for design
- Design implication: concrete recommendation the architect can act on immediately

Always cite sources (ACACIA, McCarty et al. 2025, Happle et al. 2019, CEA data) where relevant.
Never invent numbers. If data is missing, say so clearly.
"""

        user_msg = f"""
Analyse the BIPV results for this CEA project.
Goal: {goal}
Focus: {sub}
Output mode: {output_mode}

## CEA data available:
{data_summary}
"""

        with st.spinner("Analysing..."):
            response = call_claude(system, user_msg)

        st.session_state.messages.append({"role": "assistant", "content": response, "label": sub})
        st.rerun()

    # ── Conversation history ──
    for msg in reversed(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(f"**{msg.get('label', '')}**\n\n{msg['content']}")

    # ── Follow-up ──
    if st.session_state.messages:
        followup = st.chat_input("Ask a follow-up question...")
        if followup:
            threshold_ctx = build_threshold_context(threshold_result, grid_em, sc) if threshold_result else ""
            system = f"""You are a BIPV analysis assistant. Continue the conversation about the architect's CEA project results.
{threshold_ctx}
Previous analysis context is in the conversation history. Be concise and design-focused."""
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-4:]]
            history.append({"role": "user", "content": followup})

            api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "max_tokens": 800,
                      "messages": [{"role": "system", "content": system}] + history},
                timeout=60
            )
            resp.raise_for_status()
            response = resp.json()["choices"][0]["message"]["content"]

            st.session_state.messages.append({"role": "user", "content": followup, "label": "Follow-up"})
            st.session_state.messages.append({"role": "assistant", "content": response, "label": "Response"})
            st.rerun()


if __name__ == "__main__":
    main()
