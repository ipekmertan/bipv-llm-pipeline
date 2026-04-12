import streamlit as st
import zipfile
import json
import os
import io
import tempfile
import pandas as pd
from pathlib import Path
import requests

st.set_page_config(
    page_title="BIPV Analyst",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'DM Serif Display', serif; }
.main { background: #f8f7f4; }
.info-box {
    background: #fffbf0; border-left: 3px solid #c8a96e;
    padding: 0.8rem 1rem; border-radius: 0 8px 8px 0;
    margin: 1rem 0; font-size: 0.88rem;
}
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
</style>
""", unsafe_allow_html=True)

SKILLS_INDEX_PATH = Path(__file__).parent / "configuration" / "skills-index.json"
SKILLS_DIR = Path(__file__).parent / "skills"

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
    result = {"project_name": None, "files": {}, "available_simulations": [], "errors": []}
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(uploaded_file.read())) as zf:
            zf.extractall(tmpdir)
        root = Path(tmpdir)
        top = [d for d in root.iterdir() if d.is_dir()]
        if not top:
            result["errors"].append("Could not find project folder inside zip.")
            return result
        scenario = top[0]
        result["project_name"] = scenario.name

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
                        except Exception as e: result["errors"].append(f"{fname}: {e}")
                for fname in ["demand_annually.csv","demand_annually_buildings.csv","demand_seasonally.csv"]:
                    fpath = latest / "demand" / fname
                    if fpath.exists():
                        try: result["files"][fname] = pd.read_csv(fpath)
                        except Exception as e: result["errors"].append(f"{fname}: {e}")

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

        for fname in ["PHOTOVOLTAIC_PANELS.csv"]:
            fpath = scenario / "inputs" / "database" / "COMPONENTS" / "CONVERSION" / fname
            if fpath.exists():
                try: result["files"][fname] = pd.read_csv(fpath)
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
            lines.append(f"### {fname}\nShape: {df.shape[0]}x{df.shape[1]}\nColumns: {', '.join(df.columns)}\n{df.head(5).to_csv(index=False)}")
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

Instructions: Follow the skill spec for the chosen output mode and scale. Use actual numbers from the data. Plain language suitable for a design presentation. If a file is missing, say which simulation needs to be run."""

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("cea_data",None),("chat_history",[]),("skill_id",None),
              ("skill_name",None),("scale","Building"),("mode",None),("ran",False)]:
    if k not in st.session_state: st.session_state[k] = v

skills = load_skills_index()

# Build tree structure from skills index
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
            if sub not in tree[goal][mid]["children"]: tree[goal][mid]["children"][sub] = {"id": None, "children": {}}
            tree[goal][mid]["children"][sub]["children"][path[3]] = {"id": s["id"], "children": {}}
    return tree

tree_json = json.dumps(build_tree())

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

        # ── Interactive tree ───────────────────────────────────────────────────
        st.html(f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0;font-family:'DM Sans',system-ui,sans-serif;}}
body{{background:transparent;padding:4px 0 12px;}}
.wrap{{display:flex;gap:0;align-items:flex-start;overflow-x:auto;padding-bottom:8px;min-height:320px;}}
.col{{min-width:148px;max-width:148px;flex-shrink:0;}}
.col-lbl{{font-size:9px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#999;margin:0 0 7px;padding:0 8px;}}
.opt{{padding:7px 8px;margin:2px 0;border-radius:7px;font-size:12px;cursor:pointer;color:#555;border:.5px solid transparent;line-height:1.3;}}
.opt:hover{{background:#f0ede8;color:#222;}}
.opt.sel{{color:#185FA5;font-weight:500;border-color:#85B7EB;background:#E6F1FB;}}
.col.past{{opacity:.35;pointer-events:none;}}
.conn{{width:20px;flex-shrink:0;}}
.sum{{margin-top:10px;padding:7px 10px;background:#E6F1FB;border-radius:7px;font-size:11px;color:#185FA5;display:none;line-height:1.4;}}
.runbtn{{margin-top:8px;width:100%;padding:10px;background:#2d3142;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;display:none;}}
.runbtn:hover{{background:#1a1e2e;}}
</style>
<div class="wrap" id="tree">
  <div class="col" id="c-scale"><p class="col-lbl">Scale</p>
    <div class="opt" onclick="pick('scale','Building',this)">Building</div>
    <div class="opt" onclick="pick('scale','Cluster',this)">Cluster</div>
    <div class="opt" onclick="pick('scale','District',this)">District</div>
  </div>
  <div class="conn" id="cn1" style="display:none"><svg width="20" height="400" id="sv1" style="overflow:visible"><path id="p1" fill="none" stroke="#c8b89a" stroke-width="1.5" stroke-dasharray="3,2"/></svg></div>
  <div class="col" id="c-goal" style="display:none"><p class="col-lbl">Goal</p>
    <div class="opt" onclick="pick('goal','Site Potential',this)">Site Potential</div>
    <div class="opt" onclick="pick('goal','Performance Estimation',this)">Performance Estimation</div>
    <div class="opt" onclick="pick('goal','Impact and Viability',this)">Impact & Viability</div>
    <div class="opt" onclick="pick('goal','Optimize My Design',this)">Optimize My Design</div>
  </div>
  <div class="conn" id="cn2" style="display:none"><svg width="20" height="400" id="sv2" style="overflow:visible"><path id="p2" fill="none" stroke="#c8b89a" stroke-width="1.5" stroke-dasharray="3,2"/></svg></div>
  <div class="col" id="c-sub" style="display:none"><p class="col-lbl">Topic</p></div>
  <div class="conn" id="cn3" style="display:none"><svg width="20" height="400" id="sv3" style="overflow:visible"><path id="p3" fill="none" stroke="#c8b89a" stroke-width="1.5" stroke-dasharray="3,2"/></svg></div>
  <div class="col" id="c-subsub" style="display:none"><p class="col-lbl">Analysis</p></div>
  <div class="conn" id="cn4" style="display:none"><svg width="20" height="400" id="sv4" style="overflow:visible"><path id="p4" fill="none" stroke="#c8b89a" stroke-width="1.5" stroke-dasharray="3,2"/></svg></div>
  <div class="col" id="c-mode" style="display:none"><p class="col-lbl">Output mode</p>
    <div class="opt" onclick="pick('mode','Key takeaway',this)">Key takeaway</div>
    <div class="opt" onclick="pick('mode','Explain the numbers',this)">Explain the numbers</div>
    <div class="opt" onclick="pick('mode','Design implication',this)">Design implication</div>
  </div>
</div>
<div class="sum" id="sumbar"></div>
<button class="runbtn" id="runbtn" onclick="doRun()">▶ Run analysis</button>

<script>
const T={tree_json};
let S={{scale:null,goal:null,sub:null,subsub:null,mode:null,skillId:null,skillName:null}};
const $=id=>document.getElementById(id);
const show=id=>{{$(id).style.display='';}}
const hide=id=>{{$(id).style.display='none';}}
const past=id=>{{$(id).classList.add('past');}}
const unpast=id=>{{$(id).classList.remove('past');}}
const clr=col=>{{document.querySelectorAll('#'+col+' .opt').forEach(o=>o.classList.remove('sel'));}}

function drawP(sid,pid,fromEl,toId){{
  const sv=$(sid),pa=$(pid),to=$(toId);
  if(!fromEl||!to)return;
  const sr=sv.getBoundingClientRect(),fr=fromEl.getBoundingClientRect();
  const lbl=to.querySelector('.col-lbl');
  if(!lbl)return;
  const tr=lbl.getBoundingClientRect();
  const y1=fr.top+fr.height/2-sr.top, y2=tr.top+8-sr.top;
  const h=Math.max(Math.abs(y2-y1)+50,50);
  sv.setAttribute('height',h);
  pa.setAttribute('d',`M0 ${{y1}} C10 ${{y1}},10 ${{y2}},20 ${{y2}}`);
}}

function pick(type,val,el){{
  if(type==='scale'){{
    S={{scale:val,goal:null,sub:null,subsub:null,mode:null,skillId:null,skillName:null}};
    clr('c-scale');el.classList.add('sel');past('c-scale');
    ['cn2','c-sub','cn3','c-subsub','cn4','c-mode'].forEach(hide);
    show('cn1');show('c-goal');unpast('c-goal');
    setTimeout(()=>drawP('sv1','p1',el,'c-goal'),20);
  }} else if(type==='goal'){{
    S.goal=val;S.sub=null;S.subsub=null;S.mode=null;S.skillId=null;S.skillName=null;
    clr('c-goal');el.classList.add('sel');past('c-goal');
    ['cn3','c-subsub','cn4','c-mode'].forEach(hide);
    const subs=T[val];
    const col=$('c-sub');col.innerHTML='<p class="col-lbl">Topic</p>';
    Object.keys(subs).forEach(k=>{{
      const d=document.createElement('div');d.className='opt';d.textContent=k;
      d.onclick=()=>pick('sub',k,d);col.appendChild(d);
    }});
    show('cn2');show('c-sub');unpast('c-sub');
    setTimeout(()=>drawP('sv2','p2',el,'c-sub'),20);
  }} else if(type==='sub'){{
    S.sub=val;S.subsub=null;S.mode=null;S.skillId=null;S.skillName=null;
    clr('c-sub');el.classList.add('sel');
    ['cn4','c-mode'].forEach(hide);
    const node=T[S.goal][val];
    const kids=node&&node.children?Object.keys(node.children):[];
    if(kids.length>0){{
      past('c-sub');
      const col=$('c-subsub');col.innerHTML='<p class="col-lbl">Analysis</p>';
      kids.forEach(k=>{{
        const child=node.children[k];
        const d=document.createElement('div');d.className='opt';d.textContent=k;
        d.onclick=()=>{{S.skillId=child.id;S.skillName=k;pick('subsub',k,d);}};
        col.appendChild(d);
      }});
      show('cn3');show('c-subsub');unpast('c-subsub');
      setTimeout(()=>drawP('sv3','p3',el,'c-subsub'),20);
    }} else {{
      S.skillId=node?node.id:null;S.skillName=val;unpast('c-sub');
      show('cn4');show('c-mode');unpast('c-mode');
      setTimeout(()=>drawP('sv4','p4',el,'c-mode'),20);
    }}
  }} else if(type==='subsub'){{
    clr('c-subsub');el.classList.add('sel');past('c-subsub');
    show('cn4');show('c-mode');unpast('c-mode');
    setTimeout(()=>drawP('sv4','p4',el,'c-mode'),20);
  }} else if(type==='mode'){{
    S.mode=val;clr('c-mode');el.classList.add('sel');past('c-mode');
  }}
  upd();
}}

function upd(){{
  const bar=$('sumbar'),btn=$('runbtn');
  if(S.scale&&S.skillName&&S.mode){{
    bar.style.display='block';
    bar.textContent=S.scale+' · '+S.skillName+' · '+S.mode;
    btn.style.display='block';
  }} else {{bar.style.display='none';btn.style.display='none';}}
}}

function doRun(){{
  if(!S.skillId||!S.mode||!S.scale)return;
  const url=new URL(window.location.href);
  window.parent.location.href=window.parent.location.href.split('?')[0]+
    '?skill_id='+encodeURIComponent(S.skillId)+
    '&skill_name='+encodeURIComponent(S.skillName)+
    '&scale='+encodeURIComponent(S.scale)+
    '&mode='+encodeURIComponent(S.mode);
}}
</script>
""")

        # Handle query params from tree
        qp = st.query_params
        if "skill_id" in qp and not st.session_state.ran:
            st.session_state.skill_id = qp["skill_id"]
            st.session_state.skill_name = qp["skill_name"]
            st.session_state.scale = qp["scale"]
            st.session_state.mode = qp["mode"]
            st.session_state.chat_history = []
            st.session_state.ran = True

        st.markdown("---")
        if st.button("↩ Upload new project"):
            st.session_state.cea_data = None
            st.session_state.chat_history = []
            st.session_state.ran = False
            st.query_params.clear()
            st.rerun()

    with col_right:
        st.markdown("### Analysis")

        if st.session_state.ran and st.session_state.skill_id and not st.session_state.chat_history:
            skill_md = load_skill_md(st.session_state.skill_id)
            cea_summary = build_data_summary(st.session_state.cea_data)
            system_prompt = build_system_prompt(skill_md, cea_summary, st.session_state.mode, st.session_state.scale)
            user_msg = f"Run the **{st.session_state.skill_name}** analysis at **{st.session_state.scale}** scale in **{st.session_state.mode}** mode. Use only the data provided."
            st.session_state.chat_history.append({"role": "user", "content": user_msg})
            with st.spinner("Analysing…"):
                response = call_llm(system_prompt, st.session_state.chat_history)
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()

        if not st.session_state.chat_history:
            st.markdown('<div class="info-box">← Complete the tree on the left to run an analysis.</div>', unsafe_allow_html=True)

        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="bubble-user">{msg["content"]}</div><div class="clearfix"></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="bubble-ai">{msg["content"]}</div><div class="clearfix"></div>', unsafe_allow_html=True)

        if st.session_state.chat_history:
            st.markdown("---")
            followup = st.text_input("Ask a follow-up…", key="fu", placeholder="e.g. Which building has the best south facade?")
            if st.button("Send") and followup.strip():
                skill_md = load_skill_md(st.session_state.skill_id or "")
                cea_summary = build_data_summary(st.session_state.cea_data)
                system_prompt = build_system_prompt(skill_md, cea_summary, st.session_state.mode or "", st.session_state.scale or "")
                st.session_state.chat_history.append({"role": "user", "content": followup})
                with st.spinner("Thinking…"):
                    response = call_llm(system_prompt, st.session_state.chat_history)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

