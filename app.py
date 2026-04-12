import streamlit as st
import zipfile
import json
import os
import io
import tempfile
import pandas as pd
from pathlib import Path
import requests

st.set_page_config(page_title="BIPV Analyst", page_icon="☀️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'DM Serif Display', serif; }
.info-box { background:#fffbf0;border-left:3px solid #c8a96e;padding:.8rem 1rem;border-radius:0 8px 8px 0;margin:1rem 0;font-size:.88rem; }
.bubble-user { background:#2d3142;color:white;border-radius:18px 18px 4px 18px;padding:.8rem 1.1rem;margin:.5rem 0 .5rem auto;max-width:75%;width:fit-content;float:right;clear:both; }
.bubble-ai { background:white;border:1px solid #e8e4dc;border-radius:18px 18px 18px 4px;padding:.8rem 1.1rem;margin:.5rem auto .5rem 0;max-width:85%;width:fit-content;float:left;clear:both;line-height:1.65; }
.clearfix { clear:both; }
div[data-testid="stButton"] button { width: 100%; text-align: left; }
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
    return result

def build_data_summary(cea_data):
    lines = []
    if "weather_header" in cea_data["files"]:
        lines.append(f"## Location\n{cea_data['files']['weather_header']}\n")
    lines.append(f"## Available simulations\n{', '.join(cea_data['available_simulations'])}\n")
    for fname in ["solar_irradiation_annually.csv","solar_irradiation_annually_buildings.csv",
                  "solar_irradiation_seasonally.csv","demand_annually.csv",
                  "PV_PV1_total.csv","PV_PV2_total.csv","PV_PV3_total.csv","PV_PV4_total.csv",
                  "PHOTOVOLTAIC_PANELS.csv","GRID.csv","Total_demand.csv"]:
        df = cea_data["files"].get(fname)
        if df is not None:
            lines.append(f"### {fname}\n{df.shape[0]}x{df.shape[1]}\n{', '.join(df.columns)}\n{df.head(5).to_csv(index=False)}")
    return "\n".join(lines)

def call_llm(system_prompt, messages):
    api_key = st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o", "max_tokens": 1500,
                  "messages": [{"role": "system", "content": system_prompt}] + messages},
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ API error: {e}"

def build_system_prompt(skill_md, cea_summary, output_mode, scale):
    return f"""You are a BIPV expert helping architects interpret CEA4 simulation results.
Output mode: {output_mode} | Scale: {scale}

## Skill specification
{skill_md}

## CEA data
{cea_summary}

Follow the skill spec for the chosen output mode and scale. Use actual numbers from the data. Plain language for a design presentation. If a file is missing, say which CEA simulation needs to be run."""

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("cea_data", None), ("chat_history", []),
              ("tree_scale", None), ("tree_goal", None), ("tree_sub", None),
              ("tree_subsub", None), ("tree_mode", None),
              ("skill_id", None), ("skill_name", None), ("analysis_ran", False)]:
    if k not in st.session_state:
        st.session_state[k] = v

skills = load_skills_index()

# Build tree structure
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

TREE = build_tree()

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
            st.rerun()

# ── Analysis screen ────────────────────────────────────────────────────────────
else:
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### Build your analysis")
        sims = st.session_state.cea_data["available_simulations"]
        st.caption("Loaded: " + " · ".join(f"✓ {s}" for s in sims))
        st.markdown("")

        # ── Step 1: Scale ──────────────────────────────────────────────────────
        if st.session_state.tree_scale:
            st.markdown(f"**Scale** · ~~{st.session_state.tree_scale}~~" if False else f"**Scale** · *{st.session_state.tree_scale}*")
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
                    st.rerun()

        # ── Step 2: Goal ──────────────────────────────────────────────────────
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

        # ── Step 3: Topic ─────────────────────────────────────────────────────
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
                        # If no children, set skill directly
                        if not node["children"]:
                            st.session_state.skill_id = node["id"]
                            st.session_state.skill_name = topic
                        st.rerun()

        # ── Step 4: Analysis (if subtopics exist) ─────────────────────────────
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

        # ── Step 5: Output mode ───────────────────────────────────────────────
        skill_ready = st.session_state.skill_id and (
            not TREE.get(st.session_state.tree_goal, {}).get(st.session_state.tree_sub or "", {}).get("children") or
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

        # ── Run button ────────────────────────────────────────────────────────
        if st.session_state.tree_mode and st.session_state.skill_id and not st.session_state.analysis_ran:
            st.markdown("")
            if st.button("▶ Run analysis", type="primary"):
                st.session_state.chat_history = []
                st.session_state.analysis_ran = True
                st.rerun()

        # ── Start over ────────────────────────────────────────────────────────
        st.markdown("---")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("↺ Start over"):
                for k in ["tree_scale","tree_goal","tree_sub","tree_subsub","tree_mode","skill_id","skill_name","analysis_ran"]:
                    st.session_state[k] = None
                st.session_state.chat_history = []
                st.rerun()
        with col_b:
            if st.button("↩ New project"):
                for k in ["cea_data","tree_scale","tree_goal","tree_sub","tree_subsub","tree_mode","skill_id","skill_name","analysis_ran"]:
                    st.session_state[k] = None
                st.session_state.chat_history = []
                st.rerun()

    with col_right:
        st.markdown("### Analysis")

        if st.session_state.analysis_ran and st.session_state.skill_id and not st.session_state.chat_history:
            skill_md = load_skill_md(st.session_state.skill_id)
            cea_summary = build_data_summary(st.session_state.cea_data)
            system_prompt = build_system_prompt(skill_md, cea_summary, st.session_state.tree_mode, st.session_state.tree_scale)
            user_msg = f"Run the **{st.session_state.skill_name}** analysis at **{st.session_state.tree_scale}** scale in **{st.session_state.tree_mode}** mode. Use only the data provided."
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            with st.spinner("Analysing…"):
                response = call_llm(system_prompt, st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()

        if not st.session_state.chat_history:
            st.markdown('<div class="info-box">← Complete the steps on the left to run an analysis.</div>', unsafe_allow_html=True)

        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="bubble-user">{msg["content"]}</div><div class="clearfix"></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="bubble-ai">{msg["content"]}</div><div class="clearfix"></div>', unsafe_allow_html=True)

        if st.session_state.chat_history:
            st.markdown("---")
            followup = st.text_input("Ask a follow-up…", key="fu",
                                     placeholder="e.g. Which building has the best south facade?")
            if st.button("Send") and followup.strip():
                skill_md = load_skill_md(st.session_state.skill_id or "")
                cea_summary = build_data_summary(st.session_state.cea_data)
                system_prompt = build_system_prompt(skill_md, cea_summary,
                                                    st.session_state.tree_mode or "",
                                                    st.session_state.tree_scale or "")
                st.session_state.chat_history.append({"role": "user", "content": followup})
                with st.spinner("Thinking…"):
                    response = call_llm(system_prompt, st.session_state.chat_history)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

