import streamlit as st
import streamlit.components.v1 as components
import zipfile
import json
import os
import io
import tempfile
import pandas as pd
import struct
import math
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
    "site-potential--solar-availability--temporal-availability--storage-strategy": ["solar_irradiation", "pv", "demand"],
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
    "site-potential--contextual-feasibility--infrastructure-readiness": ["pv", "demand"],
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

def load_skill_md(skill_id):
    for folder in SKILLS_DIR.iterdir():
        if folder.name.strip() == skill_id:
            md = folder / "SKILL.md"
            if md.exists(): return md.read_text()
    return ""

def get_building_names(cea_data):
    df = cea_data["files"].get("solar_irradiation_annually_buildings.csv")
    if df is not None and "name" in df.columns:
        return sorted(df["name"].tolist())
    df = cea_data["files"].get("PV_PV1_total_buildings.csv")
    if df is not None and "name" in df.columns:
        return sorted(df["name"].tolist())
    return []


def _read_dbf_records(dbf_path):
    records = []
    try:
        with open(dbf_path, "rb") as f:
            header = f.read(32)
            if len(header) < 32:
                return records
            n_records = struct.unpack("<I", header[4:8])[0]
            header_len = struct.unpack("<H", header[8:10])[0]
            record_len = struct.unpack("<H", header[10:12])[0]

            fields = []
            while f.tell() < header_len:
                raw = f.read(32)
                if not raw or raw[0] == 0x0D:
                    break
                name = raw[:11].split(b"\x00", 1)[0].decode("latin1").strip()
                ftype = chr(raw[11])
                length = raw[16]
                decimals = raw[17]
                if name:
                    fields.append((name, ftype, length, decimals))

            f.seek(header_len)
            for _ in range(n_records):
                raw_record = f.read(record_len)
                if len(raw_record) < record_len or raw_record[:1] == b"*":
                    continue
                pos = 1
                row = {}
                for name, ftype, length, _decimals in fields:
                    raw_value = raw_record[pos:pos + length]
                    pos += length
                    text = raw_value.decode("latin1", errors="ignore").strip()
                    if ftype in ("N", "F"):
                        try:
                            row[name] = float(text) if text else None
                        except ValueError:
                            row[name] = None
                    elif ftype == "L":
                        row[name] = text.upper() in ("Y", "T")
                    else:
                        row[name] = text
                records.append(row)
    except Exception:
        return []
    return records


def _read_shp_bboxes(shp_path):
    bboxes = []
    try:
        with open(shp_path, "rb") as f:
            f.seek(100)
            while True:
                rec_header = f.read(8)
                if len(rec_header) < 8:
                    break
                _rec_num, content_words = struct.unpack(">2i", rec_header)
                content = f.read(content_words * 2)
                if len(content) < 4:
                    break
                shape_type = struct.unpack("<i", content[:4])[0]
                if shape_type in (3, 5, 8, 13, 15, 18, 23, 25, 28, 31) and len(content) >= 36:
                    minx, miny, maxx, maxy = struct.unpack("<4d", content[4:36])
                    bboxes.append({
                        "minx": minx,
                        "miny": miny,
                        "maxx": maxx,
                        "maxy": maxy,
                        "centroid_x": (minx + maxx) / 2,
                        "centroid_y": (miny + maxy) / 2,
                        "footprint_m2": max(0, (maxx - minx) * (maxy - miny)),
                    })
                else:
                    bboxes.append({})
    except Exception:
        return []
    return bboxes


def _read_geometry_table(shp_path):
    dbf_path = shp_path.with_suffix(".dbf")
    records = _read_dbf_records(dbf_path)
    bboxes = _read_shp_bboxes(shp_path)
    rows = []
    for idx, record in enumerate(records):
        row = dict(record)
        if idx < len(bboxes):
            row.update(bboxes[idx])
        rows.append(row)
    return pd.DataFrame(rows) if rows else None


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

        envelope = scenario / "inputs" / "building-properties" / "envelope.csv"
        if envelope.exists():
            try: result["files"]["envelope.csv"] = pd.read_csv(envelope)
            except: pass

        supply = scenario / "inputs" / "building-properties" / "supply.csv"
        if supply.exists():
            try: result["files"]["supply.csv"] = pd.read_csv(supply)
            except: pass

        supply_dir = scenario / "inputs" / "database" / "ASSEMBLIES" / "SUPPLY"
        for fname in ["SUPPLY_HEATING.csv", "SUPPLY_HOTWATER.csv", "SUPPLY_ELECTRICITY.csv", "SUPPLY_COOLING.csv"]:
            fpath = supply_dir / fname
            if fpath.exists():
                try: result["files"][fname] = pd.read_csv(fpath)
                except: pass

        thermal_dir = scenario / "outputs" / "data" / "thermal-network"
        if thermal_dir.exists():
            network_files = [str(p.relative_to(thermal_dir)) for p in thermal_dir.rglob("*.csv")]
            if network_files:
                result["files"]["thermal_network_files"] = network_files[:80]

        geometry_dir = scenario / "inputs" / "building-geometry"
        for geom_name in ["zone", "surroundings", "site"]:
            shp_path = geometry_dir / f"{geom_name}.shp"
            if shp_path.exists() and shp_path.with_suffix(".dbf").exists():
                try:
                    geom_df = _read_geometry_table(shp_path)
                    if geom_df is not None:
                        result["files"][f"{geom_name}_geometry.csv"] = geom_df
                except Exception:
                    pass

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


COMPACT_SKILL_TASKS = {
    "site-potential--solar-availability--temporal-availability--seasonal-patterns": (
        "Interpret long-term seasonal solar availability. Focus on best and weakest seasons, "
        "whether winter output remains meaningful, which surface is most seasonally stable, "
        "and whether the project should expect seasonal grid dependency rather than building-scale seasonal storage."
    ),
    "site-potential--solar-availability--temporal-availability--daily-patterns": (
        "Interpret the average 24-hour solar irradiation profile. Focus on when each surface produces, "
        "which facade supports morning or afternoon generation, and what this implies for BIPV placement "
        "and demand matching."
    ),
    "site-potential--solar-availability--surface-irradiation": (
        "Interpret annual irradiation totals by opaque surface orientation. Rank surfaces for BIPV, but "
        "do not classify against kWh/m2 thresholds unless intensity data is explicitly provided."
    ),
    "site-potential--envelope-suitability": (
        "Synthesize solar potential, available area or simulated installed area, WWR, accessibility, "
        "and visibility into a surface-by-surface BIPV suitability matrix. Identify integration opportunities "
        "and data-visible conflicts without repeating generic BIPV advice."
    ),
    "site-potential--massing-and-shading-strategy": (
        "Synthesize surrounding-building geometry, project massing, and irradiation results into massing moves "
        "that improve solar access. Focus on obstruction risk, solar-exposed surfaces, underperforming surfaces, "
        "and form changes such as stepping, setbacks, orientation, splitting mass, or moving program volume."
    ),
    "site-potential--contextual-feasibility--infrastructure-readiness": (
        "Use CEA data only as project-side infrastructure pressure: PV peak, demand peak, export pressure, "
        "grid assumptions, and supply-system compatibility. Full infrastructure readiness requires external "
        "utility/policy data; if no web-search results are provided, state that the readiness rating is provisional."
    ),
    "optimize-my-design--panel-type-tradeoff": (
        "Interpret the simulated PV panel type comparison using actual generation, installed area, yield "
        "per square metre, and panel database values where available. Avoid assuming one technology is best "
        "unless the metrics show it."
    ),
}


def _find_metric_col(df, *keywords):
    if df is None:
        return None
    for kw in keywords:
        match = next((c for c in df.columns if kw.lower() in c.lower()), None)
        if match:
            return match
    return None


def _surface_columns(df):
    return {
        "Roof": next((c for c in df.columns if "roof" in c.lower() and "window" not in c.lower()), None),
        "South wall": next((c for c in df.columns if "south" in c.lower() and "window" not in c.lower()), None),
        "East wall": next((c for c in df.columns if "east" in c.lower() and "window" not in c.lower()), None),
        "West wall": next((c for c in df.columns if "west" in c.lower() and "window" not in c.lower()), None),
        "North wall": next((c for c in df.columns if "north" in c.lower() and "window" not in c.lower()), None),
    }


def _season_col(df):
    if df is None:
        return None
    for exact in ["period", "season", "Season", "Period"]:
        if exact in df.columns:
            return exact
    return next(
        (c for c in df.columns
         if ("season" in c.lower() or "period" in c.lower())
         and "hour" not in c.lower()),
        None
    )


def _format_number(value, unit="", decimals=0):
    try:
        if pd.isna(value):
            return "not available"
        return f"{float(value):,.{decimals}f}{unit}"
    except Exception:
        return "not available"


def compute_daily_pattern_metrics(cea_data):
    df = cea_data["files"].get("solar_irradiation_hourly.csv")
    source = "solar_irradiation_hourly.csv"
    if df is None:
        return "Hourly irradiation file is not available, so an average 24-hour profile cannot be calculated reliably."

    df = df.copy()
    time_col = _find_metric_col(df, "date", "time")
    hour_col = _find_metric_col(df, "hour")
    if time_col:
        df["_dt"] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
        df["_hour"] = df["_dt"].dt.hour
    elif hour_col:
        df["_hour"] = pd.to_numeric(df[hour_col], errors="coerce")
        if df["_hour"].max() > 23:
            df["_hour"] = df["_hour"] % 24
    else:
        return f"{source} is available, but no date/time or hour column was found."

    df = df[df["_hour"].notna()]
    if df.empty:
        return f"{source} is available, but the time column could not be parsed."
    df["_hour"] = df["_hour"].astype(int)

    surfaces = {name: col for name, col in _surface_columns(df).items() if col}
    if not surfaces:
        return f"{source} is available, but no opaque surface irradiation columns were found."

    lines = [f"Source: {source}", "Metric: average hourly irradiation by hour of day (0-23), averaged across the year."]
    for surface, col in surfaces.items():
        hourly = df.groupby("_hour")[col].mean().reindex(range(24), fill_value=0)
        peak_hour = int(hourly.idxmax())
        peak_value = hourly.max()
        daily_total = hourly.sum()
        nonzero_hours = [int(h) for h, v in hourly.items() if v > 0]
        if nonzero_hours:
            active_window = f"{min(nonzero_hours):02d}:00-{max(nonzero_hours):02d}:00"
        else:
            active_window = "none"
        lines.append(
            f"- {surface}: peak at {peak_hour:02d}:00 with {_format_number(peak_value, ' kWh', 1)} average; "
            f"average-day total {_format_number(daily_total, ' kWh', 1)}; active window {active_window}."
        )
    return "\n".join(lines)


def compute_seasonal_pattern_metrics(cea_data, selected_buildings=None, scale="District"):
    df = None
    source = None
    if selected_buildings:
        df = cea_data["files"].get("solar_irradiation_seasonally_buildings.csv")
        source = "solar_irradiation_seasonally_buildings.csv"
    if df is None:
        df = cea_data["files"].get("solar_irradiation_seasonally.csv")
        source = "solar_irradiation_seasonally.csv"
    if df is None and not selected_buildings:
        df = cea_data["files"].get("solar_irradiation_seasonally_buildings.csv")
        source = "solar_irradiation_seasonally_buildings.csv"
    if df is None:
        return "Seasonal irradiation outputs are not available."

    df = df.copy()
    name_col = _find_metric_col(df, "name", "building")
    if selected_buildings and name_col:
        df = df[df[name_col].isin(selected_buildings)]
    if df.empty:
        return "Seasonal irradiation data is available, but no rows match the selected buildings."

    period_col = _season_col(df)
    if period_col is None:
        return f"{source} is available, but no season/period column was found."

    surfaces = {name: col for name, col in _surface_columns(df).items() if col}
    if not surfaces:
        return f"{source} is available, but no opaque surface irradiation columns were found."

    season_order = ["Spring", "Summer", "Autumn", "Winter"]
    df["_season"] = df[period_col].astype(str).str.strip().str.title()
    season_totals = df.groupby("_season")[[col for col in surfaces.values()]].sum()
    season_totals["__total__"] = season_totals.sum(axis=1)
    season_totals = season_totals.reindex(season_order, fill_value=0)

    total_by_season = season_totals["__total__"]
    best_season = str(total_by_season.idxmax())
    weakest_season = str(total_by_season.idxmin())
    best_value = float(total_by_season.max())
    weakest_value = float(total_by_season.min())
    annual_total = float(total_by_season.sum())

    meaningful_floor = max(annual_total * 0.01, 1.0)
    if weakest_value <= meaningful_floor:
        ratio_text = (
            f"not meaningful because {weakest_season} is near zero "
            f"({_format_number(weakest_value, ' kWh')}); treat as very high seasonal imbalance"
        )
        imbalance_class = "very high"
    else:
        ratio = best_value / weakest_value
        ratio_text = f"{ratio:.1f}:1 ({best_season} vs {weakest_season})"
        if ratio < 2:
            imbalance_class = "low"
        elif ratio <= 4:
            imbalance_class = "moderate"
        else:
            imbalance_class = "high"

    stable_rows = []
    for surface, col in surfaces.items():
        values = season_totals[col].astype(float)
        surface_total = float(values.sum())
        surface_min = float(values.min())
        surface_max = float(values.max())
        if surface_total <= 0:
            continue
        if surface_min <= max(surface_total * 0.01, 1.0):
            stability_label = "near-zero weak season"
            stability_score = None
        else:
            stability_score = surface_max / surface_min
            stability_label = f"{stability_score:.1f}:1 max/min"
        stable_rows.append({
            "surface": surface,
            "total": surface_total,
            "min": surface_min,
            "max": surface_max,
            "stability_score": stability_score,
            "stability_label": stability_label,
        })

    surfaces_with_scores = [row for row in stable_rows if row["stability_score"] is not None]
    if surfaces_with_scores:
        most_stable = min(surfaces_with_scores, key=lambda row: row["stability_score"])
        stable_text = f"{most_stable['surface']} ({most_stable['stability_label']})"
    elif stable_rows:
        most_stable = max(stable_rows, key=lambda row: row["min"])
        stable_text = (
            f"{most_stable['surface']} has the strongest weak-season output "
            f"({_format_number(most_stable['min'], ' kWh')}), but all available surfaces have a near-zero weak season"
        )
    else:
        stable_text = "not available because all surface totals are zero."

    lines = [
        f"Source: {source}",
        f"Scale: {scale}",
        "Metric: seasonal irradiation totals by opaque surface. Window irradiation is excluded.",
        f"Total seasonal irradiation across opaque surfaces: {_format_number(annual_total, ' kWh/year')}.",
        f"Best season: {best_season} with {_format_number(best_value, ' kWh')}.",
        f"Weakest season: {weakest_season} with {_format_number(weakest_value, ' kWh')}.",
        f"Seasonal imbalance ratio: {ratio_text}.",
        f"Seasonal imbalance class: {imbalance_class}.",
        f"Most stable surface: {stable_text}.",
        "Do not print infinity. If the weak season is zero or near-zero, state that the ratio is not meaningful and classify the imbalance as very high.",
        "Seasonal design meaning: building-scale batteries should not be presented as the normal solution for seasonal mismatch; frame this as grid dependency, district-scale storage, thermal storage, or lower winter self-sufficiency unless a specific seasonal storage system is provided.",
        "Season totals:",
    ]
    for season in season_order:
        lines.append(f"- {season}: {_format_number(float(total_by_season.loc[season]), ' kWh')}.")
    lines.append("Surface totals and stability:")
    for row in sorted(stable_rows, key=lambda item: item["total"], reverse=True):
        lines.append(
            f"- {row['surface']}: annual {_format_number(row['total'], ' kWh/year')}; "
            f"seasonal range {_format_number(row['min'], ' kWh')} to {_format_number(row['max'], ' kWh')}; "
            f"stability {row['stability_label']}."
        )
    return "\n".join(lines)


def compute_surface_irradiation_metrics(cea_data, selected_buildings=None, scale="District"):
    df = cea_data["files"].get("solar_irradiation_annually_buildings.csv")
    source = "solar_irradiation_annually_buildings.csv"
    if df is None:
        df = cea_data["files"].get("solar_irradiation_annually.csv")
        source = "solar_irradiation_annually.csv"
    if df is None:
        return "Annual irradiation outputs are not available."

    df = df.copy()
    name_col = _find_metric_col(df, "name", "building")
    if selected_buildings and name_col:
        df = df[df[name_col].isin(selected_buildings)]
    if df.empty:
        return "Annual irradiation data is available, but no rows match the selected buildings."

    surfaces = {name: col for name, col in _surface_columns(df).items() if col}
    if not surfaces:
        return f"{source} is available, but no opaque surface irradiation columns were found."

    totals = {surface: float(df[col].sum()) for surface, col in surfaces.items()}
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    total_all = sum(totals.values())
    lines = [
        f"Source: {source}",
        f"Scale: {scale}",
        "Important limitation: values are total annual kWh, not kWh/m2 intensity. Use them for relative ranking unless surface areas are supplied.",
        f"Total opaque-surface irradiation: {_format_number(total_all, ' kWh/year')}.",
        f"Best surface by total irradiation: {ranked[0][0]} ({_format_number(ranked[0][1], ' kWh/year')}).",
        f"Weakest surface by total irradiation: {ranked[-1][0]} ({_format_number(ranked[-1][1], ' kWh/year')}).",
        "Surface ranking:",
    ]
    for surface, value in ranked:
        share = (value / total_all * 100) if total_all else 0
        lines.append(f"- {surface}: {_format_number(value, ' kWh/year')} ({share:.1f}% of opaque-surface total).")
    return "\n".join(lines)


def compute_envelope_suitability_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    irr_df = files.get("solar_irradiation_annually_buildings.csv")
    irr_source = "solar_irradiation_annually_buildings.csv"
    if irr_df is None:
        irr_df = files.get("solar_irradiation_annually.csv")
        irr_source = "solar_irradiation_annually.csv"
    if irr_df is None:
        return "Annual irradiation data is not available, so envelope suitability cannot be grounded in solar potential."

    irr_df = irr_df.copy()
    name_col = _find_metric_col(irr_df, "name", "building")
    if selected_buildings and name_col:
        irr_df = irr_df[irr_df[name_col].isin(selected_buildings)]
    if irr_df.empty:
        return "Annual irradiation data is available, but no rows match the selected buildings."

    envelope_df = files.get("envelope.csv")
    if envelope_df is not None:
        envelope_df = envelope_df.copy()
        env_name_col = _find_metric_col(envelope_df, "name", "building")
        if selected_buildings and env_name_col:
            envelope_df = envelope_df[envelope_df[env_name_col].isin(selected_buildings)]

    pv_area_df = None
    pv_area_source = None
    for ptype in ["PV1", "PV2", "PV3", "PV4"]:
        candidate = files.get(f"PV_{ptype}_total_buildings.csv")
        if candidate is not None:
            pv_area_df = candidate.copy()
            pv_area_source = f"PV_{ptype}_total_buildings.csv"
            break
    if pv_area_df is not None:
        pv_name_col = _find_metric_col(pv_area_df, "name", "building")
        if selected_buildings and pv_name_col:
            pv_area_df = pv_area_df[pv_area_df[pv_name_col].isin(selected_buildings)]

    surfaces = {name: col for name, col in _surface_columns(irr_df).items() if col}
    if not surfaces:
        return f"{irr_source} is available, but no opaque surface irradiation columns were found."

    area_cols = {
        "Roof": "PV_roofs_top_m2",
        "South wall": "PV_walls_south_m2",
        "East wall": "PV_walls_east_m2",
        "West wall": "PV_walls_west_m2",
        "North wall": "PV_walls_north_m2",
    }
    wwr_cols = {
        "South wall": "wwr_south",
        "East wall": "wwr_east",
        "West wall": "wwr_west",
        "North wall": "wwr_north",
    }

    irradiation_totals = {surface: float(irr_df[col].sum()) for surface, col in surfaces.items()}
    max_irradiation = max(irradiation_totals.values()) if irradiation_totals else 0
    total_irradiation = sum(irradiation_totals.values())

    rows = []
    for surface, irradiation in irradiation_totals.items():
        solar_share = (irradiation / total_irradiation * 100) if total_irradiation else 0
        solar_score = (irradiation / max_irradiation) if max_irradiation else 0

        installed_area = None
        area_col = area_cols.get(surface)
        if pv_area_df is not None and area_col in pv_area_df.columns:
            installed_area = float(pv_area_df[area_col].sum())

        wwr = None
        if envelope_df is not None and surface in wwr_cols and wwr_cols[surface] in envelope_df.columns:
            wwr = float(pd.to_numeric(envelope_df[wwr_cols[surface]], errors="coerce").mean())

        if surface == "Roof":
            access = "medium: usually reachable, but roof equipment and access paths can reduce usable area"
            visibility = "low: often the least visible BIPV surface from street level"
            constructability_score = 1.0
        else:
            if wwr is None:
                constructability_score = 0.6
                continuity = "unknown WWR"
            elif wwr <= 0.35:
                constructability_score = 0.9
                continuity = "low glazing, likely more continuous opaque area"
            elif wwr <= 0.6:
                constructability_score = 0.65
                continuity = "moderate glazing, selective facade zones likely"
            else:
                constructability_score = 0.35
                continuity = "high glazing, fragmented opaque area likely"
            access = f"medium: vertical installation and maintenance access needed; {continuity}"
            visibility = "high: facade BIPV will be architecturally visible"

        if installed_area is not None and installed_area <= 0 and surface != "Roof":
            area_note = "no PV area was simulated on this facade"
            area_score = 0.35
        elif installed_area is not None:
            area_note = f"simulated PV area {_format_number(installed_area, ' m2', 1)}"
            area_score = min(installed_area / 500, 1.0)
        else:
            area_note = "surface area not extracted; use WWR and irradiation as proxies"
            area_score = constructability_score

        score = (0.45 * solar_score) + (0.25 * area_score) + (0.20 * constructability_score) + (0.10 if surface == "Roof" else 0.08)
        if score >= 0.68:
            suitability = "HIGH"
        elif score >= 0.42:
            suitability = "MEDIUM"
        else:
            suitability = "LOW"

        rows.append({
            "surface": surface,
            "irradiation": irradiation,
            "solar_share": solar_share,
            "wwr": wwr,
            "area_note": area_note,
            "access": access,
            "visibility": visibility,
            "suitability": suitability,
            "score": score,
        })

    rows = sorted(rows, key=lambda item: item["score"], reverse=True)
    high_rows = [row for row in rows if row["suitability"] == "HIGH"]
    visible_high = [row for row in high_rows if "facade" in row["visibility"]]
    roof_row = next((row for row in rows if row["surface"] == "Roof"), None)

    lines = [
        f"Sources: {irr_source}; envelope.csv {'available' if envelope_df is not None else 'not available'}; {pv_area_source or 'no PV building area file available'}.",
        f"Scale: {scale}",
        "Suitability combines solar potential, simulated PV area when available, WWR/continuity, accessibility, and visibility. Visibility/accessibility are early-design heuristics, not measured site-survey data.",
        "Suitability matrix:",
    ]
    for row in rows:
        wwr_text = _format_number(row["wwr"] * 100, '%', 0) if row["wwr"] is not None else "not available"
        lines.append(
            f"- {row['surface']}: solar {_format_number(row['irradiation'], ' kWh/year')} "
            f"({row['solar_share']:.1f}% of opaque-surface irradiation); WWR {wwr_text}; "
            f"{row['area_note']}; access {row['access']}; visibility {row['visibility']}; "
            f"suitability {row['suitability']}."
        )

    lines.append("Integration opportunities:")
    if roof_row and roof_row["suitability"] in ["HIGH", "MEDIUM"]:
        lines.append(f"- Roof: {roof_row['suitability']} suitability with low visibility; treat as the least aesthetically constrained BIPV surface.")
    if visible_high:
        for row in visible_high:
            lines.append(f"- {row['surface']}: high suitability and high visibility; treat BIPV as an architectural facade decision, not only a technical add-on.")
    if not visible_high and high_rows:
        lines.append("- High-suitability surfaces are mostly low-visibility or technically dominant; facade expression may need a separate design argument.")

    visible_facades = [row for row in rows if row["surface"] != "Roof" and row["suitability"] in ["HIGH", "MEDIUM"]]
    if visible_facades:
        lines.append("Visible-facade BIPV option names to suggest when relevant:")
        lines.append("- Opaque BIPV facade cladding / BIPV rainscreen: for solid wall zones where PV can replace conventional facade panels.")
        lines.append("- Colored or patterned BIPV modules: for prominent elevations where module appearance must be coordinated with facade design.")
        lines.append("- Semi-transparent BIPV glazing: for glazed zones where daylight and view should be retained while generating electricity.")
        lines.append("- BIPV curtain wall or PV spandrel panels: for office/commercial facades with repeated facade modules.")
        lines.append("- PV shading devices / BIPV louvers: for facades where solar control, daylight control, and generation can be combined.")
        lines.append("- Ventilated BIPV facade / BIPV-T facade: for assemblies where rear ventilation or heat recovery is part of the design concept.")

    conflicts = []
    if pv_area_df is not None:
        high_solar_facades = [
            row for row in rows
            if row["surface"] != "Roof"
            and row["solar_share"] >= 10
            and "no PV area was simulated" in row["area_note"]
        ]
        for row in high_solar_facades:
            conflicts.append(
                f"{row['surface']} has meaningful irradiation ({row['solar_share']:.1f}% share) but no simulated PV area; check whether facade PV was excluded in the simulation setup."
            )
    if envelope_df is None:
        conflicts.append("envelope.csv is missing, so WWR/opaque-area suitability cannot be checked.")

    lines.append("Conflict flags:")
    if conflicts:
        for conflict in conflicts:
            lines.append(f"- {conflict}")
    else:
        lines.append("- No data-visible conflict detected. User design intentions such as terraces, heritage constraints, or planned equipment zones are not included in the CEA files.")

    return "\n".join(lines)


def _height_col(df):
    return _find_metric_col(df, "height_ag", "height", "floors_ag", "floors")


def _height_value(row, col):
    if not col or col not in row:
        return None
    value = row[col]
    try:
        value = float(value)
    except Exception:
        return None
    if "floor" in col.lower():
        return value * 3.2
    return value


def _bbox_gap(a, b):
    dx = max(float(a["minx"]) - float(b["maxx"]), float(b["minx"]) - float(a["maxx"]), 0)
    dy = max(float(a["miny"]) - float(b["maxy"]), float(b["miny"]) - float(a["maxy"]), 0)
    return math.hypot(dx, dy)


def _direction_from_to(source, target):
    dx = float(target["centroid_x"]) - float(source["centroid_x"])
    dy = float(target["centroid_y"]) - float(source["centroid_y"])
    if abs(dx) > abs(dy):
        return "east" if dx > 0 else "west"
    return "north" if dy > 0 else "south"


def _obstruction_level(score):
    if score >= 4:
        return "very high"
    if score >= 2:
        return "high"
    if score >= 1:
        return "moderate"
    return "low"


def compute_massing_shading_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    irr_df = files.get("solar_irradiation_annually_buildings.csv")
    if irr_df is None:
        return "Building-level annual irradiation is not available, so massing/shading strategy cannot identify which buildings or surfaces are constrained."

    irr_df = irr_df.copy()
    irr_name_col = _find_metric_col(irr_df, "name", "building")
    if selected_buildings and irr_name_col:
        irr_df = irr_df[irr_df[irr_name_col].isin(selected_buildings)]
    if irr_df.empty:
        return "Annual irradiation data is available, but no rows match the selected buildings."

    zone_df = files.get("zone_geometry.csv")
    surroundings_df = files.get("surroundings_geometry.csv")
    zone_name_col = _find_metric_col(zone_df, "name", "building") if zone_df is not None else None
    zone_height_col = _height_col(zone_df) if zone_df is not None else None
    surroundings_name_col = _find_metric_col(surroundings_df, "name", "building") if surroundings_df is not None else None
    surroundings_height_col = _height_col(surroundings_df) if surroundings_df is not None else None

    selected_zone = zone_df.copy() if zone_df is not None else None
    if selected_zone is not None and selected_buildings and zone_name_col:
        selected_zone = selected_zone[selected_zone[zone_name_col].isin(selected_buildings)]

    surfaces = {name: col for name, col in _surface_columns(irr_df).items() if col}
    if not surfaces:
        return "Annual irradiation data is available, but no opaque surface irradiation columns were found."

    rows = []
    for _, row in irr_df.iterrows():
        bname = str(row[irr_name_col]) if irr_name_col else "selected area"
        surface_values = {surface: float(row[col]) for surface, col in surfaces.items()}
        total = sum(surface_values.values())
        best_surface = max(surface_values, key=surface_values.get)
        weakest_surface = min(surface_values, key=surface_values.get)
        roof = surface_values.get("Roof", 0)
        best_facade = max(
            [(s, v) for s, v in surface_values.items() if s != "Roof"],
            key=lambda item: item[1],
            default=(None, 0),
        )
        rows.append({
            "name": bname,
            "total": total,
            "best_surface": best_surface,
            "weakest_surface": weakest_surface,
            "roof": roof,
            "best_facade": best_facade[0],
            "best_facade_value": best_facade[1],
            "surface_values": surface_values,
        })

    ranked = sorted(rows, key=lambda item: item["total"], reverse=True)
    weakest = sorted(rows, key=lambda item: item["total"])

    lines = [
        "Sources: solar_irradiation_annually_buildings.csv; "
        f"zone_geometry.csv {'available' if zone_df is not None else 'not available'}; "
        f"surroundings_geometry.csv {'available' if surroundings_df is not None else 'not available'}.",
        f"Scale: {scale}",
        "CEA irradiation already includes shading from the surroundings file. Do not apply another shading penalty; use geometry to interpret likely causes and massing responses.",
        "At building scale, still check the selected building against all other project buildings in zone_geometry.csv. A single selected building can be shaded by the rest of the project, not only by external surroundings.",
        "Solar-access ranking:",
    ]
    for item in ranked[:8]:
        lines.append(
            f"- {item['name']}: total opaque-surface irradiation {_format_number(item['total'], ' kWh/year')}; "
            f"best surface {item['best_surface']}; best facade {item['best_facade'] or 'not available'} "
            f"({_format_number(item['best_facade_value'], ' kWh/year')}); weakest surface {item['weakest_surface']}."
        )

    if len(rows) > 1:
        lines.append(
            f"Strongest solar-access building: {ranked[0]['name']} ({_format_number(ranked[0]['total'], ' kWh/year')})."
        )
        lines.append(
            f"Most constrained selected building by total irradiation: {weakest[0]['name']} ({_format_number(weakest[0]['total'], ' kWh/year')})."
        )

    geometry_ok = (
        selected_zone is not None and not selected_zone.empty
        and zone_df is not None and not zone_df.empty
        and all(c in selected_zone.columns for c in ["minx", "miny", "maxx", "maxy", "centroid_x", "centroid_y"])
        and all(c in zone_df.columns for c in ["minx", "miny", "maxx", "maxy", "centroid_x", "centroid_y"])
    )

    obstruction_notes = []
    obstruction_rankings = []
    if geometry_ok:
        for _, building in selected_zone.iterrows():
            bname = str(building[zone_name_col]) if zone_name_col else "selected building"
            bheight = _height_value(building, zone_height_col) or 0
            external_candidates = []
            internal_candidates = []
            neighbour_sources = []
            if surroundings_df is not None and not surroundings_df.empty:
                neighbour_sources.append(("external surrounding", surroundings_df, surroundings_name_col, surroundings_height_col))
            neighbour_sources.append(("project building", zone_df, zone_name_col, zone_height_col))

            for source_type, source_df, source_name_col, source_height_col in neighbour_sources:
                for _, neighbour in source_df.iterrows():
                    nname = str(neighbour[source_name_col]) if source_name_col else source_type
                    if nname == bname:
                        continue
                    nheight = _height_value(neighbour, source_height_col) or 0
                    distance = _bbox_gap(building, neighbour)
                    direction = _direction_from_to(building, neighbour)
                    critical_distance = max(nheight * 2, 1)
                    if distance <= critical_distance or nheight > bheight:
                        influence_ratio = critical_distance / max(distance, 1)
                        height_ratio = nheight / max(bheight, 1)
                        side_weight = 1.25 if direction == "south" else 1.0 if direction in ("east", "west") else 0.65
                        risk_score = influence_ratio * max(height_ratio, 0.25) * side_weight
                        candidate = {
                            "name": nname,
                            "height": nheight,
                            "distance": distance,
                            "direction": direction,
                            "critical_distance": critical_distance,
                            "taller": nheight > bheight,
                            "source_type": source_type,
                            "risk_score": risk_score,
                            "influence_ratio": influence_ratio,
                        }
                        if source_type == "project building":
                            internal_candidates.append(candidate)
                        else:
                            external_candidates.append(candidate)
                        obstruction_rankings.append({
                            "target": bname,
                            **candidate,
                        })

            external_candidates = sorted(external_candidates, key=lambda item: item["risk_score"], reverse=True)[:5]
            internal_candidates = sorted(internal_candidates, key=lambda item: item["risk_score"], reverse=True)[:5]

            if external_candidates:
                lines.append(f"External obstruction context for {bname} (height approx. {_format_number(bheight, ' m', 1)}):")
                for c in external_candidates:
                    taller_text = "taller than target" if c["taller"] else "not taller than target"
                    lines.append(
                        f"- {c['name']}: {c['direction']} side; height {_format_number(c['height'], ' m', 1)}; "
                        f"gap approx. {_format_number(c['distance'], ' m', 1)}; {taller_text}; "
                        f"2H influence distance approx. {_format_number(c['critical_distance'], ' m', 1)}."
                    )
                    if c["direction"] == "south":
                        obstruction_notes.append(f"{bname}: external south-side obstruction may reduce roof/south-facade winter solar access.")
                    elif c["direction"] in ("east", "west"):
                        obstruction_notes.append(f"{bname}: external {c['direction']}-side obstruction may reduce morning/afternoon facade usefulness.")

            if internal_candidates:
                lines.append(f"Project-to-project obstruction context for {bname}:")
                for c in internal_candidates:
                    taller_text = "taller than target" if c["taller"] else "not taller than target"
                    lines.append(
                        f"- {c['name']}: {c['direction']} side; height {_format_number(c['height'], ' m', 1)}; "
                        f"gap approx. {_format_number(c['distance'], ' m', 1)}; {taller_text}; "
                        f"2H influence distance approx. {_format_number(c['critical_distance'], ' m', 1)}."
                    )
                    if c["direction"] == "south":
                        obstruction_notes.append(f"{bname}: project building {c['name']} to the south may cause mutual shading; consider stepping, spacing, or shifting height.")
                    elif c["direction"] in ("east", "west"):
                        obstruction_notes.append(f"{bname}: project building {c['name']} to the {c['direction']} may affect morning/afternoon facade strategy.")
            else:
                lines.append(f"Project-to-project obstruction context for {bname}: no nearby/tall project building was flagged by the 2H screening rule.")
    else:
        lines.append("Project geometry is not available or lacks usable bboxes/heights, so obstruction causes cannot be assigned to specific neighbours.")

    if obstruction_notes:
        lines.append("Likely shading constraints:")
        for note in sorted(set(obstruction_notes))[:8]:
            lines.append(f"- {note}")

    if obstruction_rankings:
        lines.append("Ranked obstruction risk by side (geometry screening, not exact kWh loss):")
        for c in sorted(obstruction_rankings, key=lambda item: item["risk_score"], reverse=True)[:12]:
            source_label = "project" if c["source_type"] == "project building" else "surrounding"
            level = _obstruction_level(c["risk_score"])
            lines.append(
                f"- {c['target']} {c['direction']} side: {source_label} building {c['name']}; "
                f"{level} obstruction risk; height {_format_number(c['height'], ' m', 1)}; "
                f"gap {_format_number(c['distance'], ' m', 1)}; 2H/gap ratio {c['influence_ratio']:.2f}."
            )
        lines.append("Use the ranked obstruction list to say which side is most constrained and by which building. Do not mention the internal numeric risk score and do not call this a simulated shading loss.")

    lines.append("Massing strategy options to consider:")
    lines.append("- Preserve or expand the highest-irradiation roof plane as the baseline solar collector.")
    lines.append("- Step down massing toward the south where southern obstructions or project-to-project obstruction are likely.")
    lines.append("- Increase setbacks from tall south/east/west neighbours where the gap is within roughly 2x neighbour height.")
    lines.append("- Shift height or dense program volume toward the north side of the plot to keep southern roof/facade exposure clearer.")
    lines.append("- Elongate the building east-west when the goal is a larger south-facing BIPV facade; split bulky volumes if that reduces project-to-project obstruction or over-deep massing.")
    lines.append("- If a facade is persistently weak, deprioritise it for PV and use it for windows, access, services, or conventional cladding.")
    lines.append("- If the optimal solar form differs strongly from the current massing, state that the massing itself should be renegotiated rather than merely placing panels on poor surfaces.")
    lines.append("Performance-based massing option names to suggest when relevant:")
    lines.append("- Subtractive massing: remove parts of a larger starting volume to create better solar exposure instead of only moving panels.")
    lines.append("- Courtyard massing: carve an internal void when it can increase useful facade exposure and daylight access without over-shading the lower levels.")
    lines.append("- Atrium massing: use a taller internal void when solar/daylight access and program organisation both benefit.")
    lines.append("- Stilted / lifted massing: lift part of the volume when ground-level porosity, daylight, or overshadowing reduction matters.")
    lines.append("- Solar-envelope massing: shape the allowed volume so it preserves solar access for itself or neighbours.")
    lines.append("- Split-bar massing: divide a bulky volume into thinner bars to reduce project-to-project obstruction or over-deep massing and expose more roof/facade surface.")
    lines.append("- Terraced / stepped massing: reduce height toward the solar-critical side and use upper setbacks as solar roof planes.")

    return "\n".join(lines)


def _lookup_supply_descriptions(supply_df, lookup_df, code_col_name):
    if supply_df is None or lookup_df is None or code_col_name not in supply_df.columns:
        return []
    code_col = _find_metric_col(lookup_df, "code")
    desc_col = _find_metric_col(lookup_df, "description")
    if not code_col or not desc_col:
        return []
    lookup = {
        str(row[code_col]): str(row[desc_col])
        for _, row in lookup_df.iterrows()
    }
    descriptions = []
    for code in supply_df[code_col_name].dropna().astype(str).unique():
        descriptions.append(f"{code}: {lookup.get(code, 'description not found')}")
    return descriptions


def compute_infrastructure_readiness_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})

    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total.csv")
                     and "buildings" not in k), None)
    pv_df = files.get(pv_fname) if pv_fname else None
    pv_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None

    demand_df = files.get("Total_demand_hourly.csv")
    demand_source = "Total_demand_hourly.csv"
    if selected_buildings:
        demand_frames = []
        for bname in selected_buildings:
            df = files.get(f"{bname}.csv")
            if df is not None:
                demand_frames.append(df)
        if demand_frames:
            demand_df = pd.concat(demand_frames, ignore_index=True)
            demand_source = "selected building hourly demand files"
    demand_col = _find_metric_col(demand_df, "E_sys_kWh", "GRID", "E_tot") if demand_df is not None else None

    peak_pv_kw = float(pv_df[pv_col].max()) if pv_df is not None and pv_col else None
    annual_pv_kwh = float(pv_df[pv_col].sum()) if pv_df is not None and pv_col else None
    peak_demand_kw = float(demand_df[demand_col].max()) if demand_df is not None and demand_col else None
    annual_demand_kwh = float(demand_df[demand_col].sum()) if demand_df is not None and demand_col else None

    pv_to_demand_peak = (peak_pv_kw / peak_demand_kw) if peak_pv_kw is not None and peak_demand_kw and peak_demand_kw > 0 else None
    pv_to_demand_annual = (annual_pv_kwh / annual_demand_kwh) if annual_pv_kwh is not None and annual_demand_kwh and annual_demand_kwh > 0 else None

    transformer_assumption_kva = 630
    transformer_ratio = peak_pv_kw / transformer_assumption_kva if peak_pv_kw is not None else None
    if transformer_ratio is None:
        readiness = "UNKNOWN"
    elif transformer_ratio < 0.25:
        readiness = "STRONG"
    elif transformer_ratio <= 0.75:
        readiness = "MODERATE"
    else:
        readiness = "CONSTRAINED"

    grid_df = files.get("GRID.csv")
    grid_carbon = buy_price = sell_price = None
    if grid_df is not None:
        carbon_col = _find_metric_col(grid_df, "GHG_kgCO2MJ", "CO2", "GHG")
        buy_col = _find_metric_col(grid_df, "Opex_var_buy", "buy")
        sell_col = _find_metric_col(grid_df, "Opex_var_sell", "sell")
        if carbon_col:
            grid_carbon = float(pd.to_numeric(grid_df[carbon_col], errors="coerce").mean()) * 3.6
        if buy_col:
            buy_price = float(pd.to_numeric(grid_df[buy_col], errors="coerce").mean())
        if sell_col:
            sell_price = float(pd.to_numeric(grid_df[sell_col], errors="coerce").mean())

    supply_df = files.get("supply.csv")
    if supply_df is not None and selected_buildings:
        name_col = _find_metric_col(supply_df, "name", "building")
        if name_col:
            supply_df = supply_df[supply_df[name_col].isin(selected_buildings)]

    heating = _lookup_supply_descriptions(supply_df, files.get("SUPPLY_HEATING.csv"), "supply_type_hs")
    hotwater = _lookup_supply_descriptions(supply_df, files.get("SUPPLY_HOTWATER.csv"), "supply_type_dhw")
    electricity = _lookup_supply_descriptions(supply_df, files.get("SUPPLY_ELECTRICITY.csv"), "supply_type_el")
    cooling = _lookup_supply_descriptions(supply_df, files.get("SUPPLY_COOLING.csv"), "supply_type_cs")

    thermal_files = files.get("thermal_network_files")
    dh_present = bool(thermal_files and any("/DH/" in f or f.startswith("DH/") for f in thermal_files))
    dc_present = bool(thermal_files and any("/DC/" in f or f.startswith("DC/") for f in thermal_files))

    lines = [
        f"Sources: {pv_fname or 'no PV total file'}; {demand_source if demand_df is not None else 'no hourly demand file'}; GRID.csv {'available' if grid_df is not None else 'not available'}; supply.csv {'available' if supply_df is not None else 'not available'}.",
        f"Scale: {scale}",
        f"Project-side infrastructure pressure from CEA screening: {readiness}.",
        "Full infrastructure readiness cannot be confirmed from CEA alone. Local transformer capacity, grid export caps, permitting timelines, net metering, feed-in tariffs, and utility approval rules require external web/utility data.",
        "Grid/export screening:",
    ]
    lines.append(f"- Peak PV generation: {_format_number(peak_pv_kw, ' kW', 1)}.")
    lines.append(f"- Annual PV generation: {_format_number(annual_pv_kwh, ' kWh/year')}.")
    lines.append(f"- Peak electricity demand: {_format_number(peak_demand_kw, ' kW', 1)}.")
    lines.append(f"- Annual electricity demand: {_format_number(annual_demand_kwh, ' kWh/year')}.")
    lines.append(f"- PV peak / demand peak: {_format_number(pv_to_demand_peak * 100 if pv_to_demand_peak is not None else None, '%', 1)}.")
    lines.append(f"- PV annual generation / annual demand: {_format_number(pv_to_demand_annual * 100 if pv_to_demand_annual is not None else None, '%', 1)}.")
    lines.append(
        f"- Transformer screening: peak PV is {_format_number(transformer_ratio * 100 if transformer_ratio is not None else None, '%', 1)} "
        f"of an indicative {transformer_assumption_kva} kVA neighbourhood transformer. Replace this assumption with actual utility data when available."
    )

    if grid_carbon is not None or buy_price is not None or sell_price is not None:
        lines.append("Grid assumptions from GRID.csv:")
        lines.append(f"- Grid carbon factor: {_format_number(grid_carbon, ' kgCO2/kWh', 3)}.")
        lines.append(f"- Grid buy price: {_format_number(buy_price, ' currency/kWh', 3)}.")
        lines.append(f"- Grid sell price: {_format_number(sell_price, ' currency/kWh', 3)}.")

    lines.append("Supply-system compatibility:")
    if electricity:
        lines.append(f"- Electricity supply: {'; '.join(electricity)}.")
    if heating:
        lines.append(f"- Heating supply: {'; '.join(heating)}.")
    if hotwater:
        lines.append(f"- Hot water supply: {'; '.join(hotwater)}.")
    if cooling:
        lines.append(f"- Cooling supply: {'; '.join(cooling)}.")
    if dh_present or dc_present:
        networks = []
        if dh_present:
            networks.append("district heating network outputs found")
        if dc_present:
            networks.append("district cooling network outputs found")
        lines.append(f"- Thermal-network context: {', '.join(networks)}.")
    else:
        lines.append("- Thermal-network context: no district heating/cooling network output was detected in the extracted results.")

    lines.append("Interpretation rules:")
    lines.append("- If PV peak is large relative to demand peak or assumed transformer capacity, frame readiness as export-constrained and prioritise self-consumption, load shifting, or storage.")
    lines.append("- If heating is boiler/district-heating based, BIPV electricity does not directly offset heating carbon unless heat pumps or electric heating are part of the system definition.")
    lines.append("- If heat pumps/electric cooling are present, align PV production with those electrical loads before maximising export.")
    lines.append("- Do not claim net metering, feed-in tariff, or utility approval status unless an external search module supplies that information.")
    return "\n".join(lines)


def compute_panel_tradeoff_metrics(cea_data, selected_buildings=None):
    files = cea_data.get("files", {})
    panel_db = files.get("PHOTOVOLTAIC_PANELS.csv")
    panel_lookup = {}
    if panel_db is not None:
        code_col = _find_metric_col(panel_db, "code")
        if code_col:
            for _, row in panel_db.iterrows():
                panel_lookup[str(row[code_col])] = row

    rows = []
    for ptype in ["PV1", "PV2", "PV3", "PV4"]:
        df = files.get(f"PV_{ptype}_total_buildings.csv")
        source = f"PV_{ptype}_total_buildings.csv"
        if df is None:
            df = files.get(f"PV_{ptype}_total.csv")
            source = f"PV_{ptype}_total.csv"
        if df is None:
            continue

        df = df.copy()
        name_col = _find_metric_col(df, "name", "building")
        if selected_buildings and name_col:
            df = df[df[name_col].isin(selected_buildings)]
        if df.empty:
            continue

        gen_col = _find_metric_col(df, "E_PV_gen", "E_PV", "electricity")
        area_col = _find_metric_col(df, "Area_PV", "area_pv", "m2")
        annual_gen = float(df[gen_col].sum()) if gen_col else 0
        area = float(df[area_col].sum()) if area_col else 0
        yield_m2 = annual_gen / area if area else None

        db_row = panel_lookup.get(ptype)
        description = ptype
        efficiency = embodied = facade_cost = roof_cost = None
        if db_row is not None:
            desc_col = _find_metric_col(panel_db, "description")
            eff_col = _find_metric_col(panel_db, "PV_n", "efficiency")
            emb_col = _find_metric_col(panel_db, "module_embodied", "embodied", "CO2")
            facade_cost_col = _find_metric_col(panel_db, "cost_facade", "facade")
            roof_cost_col = _find_metric_col(panel_db, "cost_roof", "roof")
            description = str(db_row[desc_col]) if desc_col else ptype
            efficiency = db_row[eff_col] if eff_col else None
            embodied = db_row[emb_col] if emb_col else None
            facade_cost = db_row[facade_cost_col] if facade_cost_col else None
            roof_cost = db_row[roof_cost_col] if roof_cost_col else None

        rows.append({
            "ptype": ptype,
            "description": description,
            "source": source,
            "annual_gen": annual_gen,
            "area": area,
            "yield_m2": yield_m2,
            "efficiency": efficiency,
            "embodied": embodied,
            "facade_cost": facade_cost,
            "roof_cost": roof_cost,
        })

    if not rows:
        return "No PV panel type result files are available for comparison."

    ranked_generation = sorted(rows, key=lambda r: r["annual_gen"], reverse=True)
    ranked_yield = sorted([r for r in rows if r["yield_m2"] is not None], key=lambda r: r["yield_m2"], reverse=True)
    lines = [
        "Source: simulated PV result files plus PHOTOVOLTAIC_PANELS.csv when available.",
        f"Panel types found: {', '.join(r['ptype'] for r in rows)}.",
        f"Highest total generation: {ranked_generation[0]['ptype']} ({ranked_generation[0]['description']}) with {_format_number(ranked_generation[0]['annual_gen'], ' kWh/year')}.",
    ]
    if ranked_yield:
        lines.append(
            f"Highest yield per installed area: {ranked_yield[0]['ptype']} ({ranked_yield[0]['description']}) "
            f"with {_format_number(ranked_yield[0]['yield_m2'], ' kWh/m2/year', 1)}."
        )
    lines.append("Panel comparison:")
    for row in rows:
        lines.append(
            f"- {row['ptype']} ({row['description']}): generation {_format_number(row['annual_gen'], ' kWh/year')}; "
            f"area {_format_number(row['area'], ' m2', 1)}; yield {_format_number(row['yield_m2'], ' kWh/m2/year', 1)}; "
            f"efficiency {_format_number(float(row['efficiency']) * 100 if row['efficiency'] is not None else None, '%', 1)}; "
            f"embodied carbon {_format_number(row['embodied'], ' kgCO2/m2', 1)}; "
            f"roof cost {_format_number(row['roof_cost'], ' currency/m2', 1)}; facade cost {_format_number(row['facade_cost'], ' currency/m2', 1)}."
        )
    return "\n".join(lines)


def compute_compact_metrics(skill_id, cea_data, selected_buildings=None, scale="District"):
    if skill_id == "site-potential--solar-availability--temporal-availability--seasonal-patterns":
        return compute_seasonal_pattern_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--solar-availability--temporal-availability--daily-patterns":
        return compute_daily_pattern_metrics(cea_data)
    if skill_id == "site-potential--solar-availability--surface-irradiation":
        return compute_surface_irradiation_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--envelope-suitability":
        return compute_envelope_suitability_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--massing-and-shading-strategy":
        return compute_massing_shading_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--contextual-feasibility--infrastructure-readiness":
        return compute_infrastructure_readiness_metrics(cea_data, selected_buildings, scale)
    if skill_id == "optimize-my-design--panel-type-tradeoff":
        return compute_panel_tradeoff_metrics(cea_data, selected_buildings)
    return None


def call_llm(system_prompt, messages):
    import time
    api_key = st.secrets.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))
    # Use faster model for explain/design modes — higher Groq rate limit
    if "Explain the numbers" in system_prompt or "Design implication" in system_prompt:
        model = "llama-3.1-8b-instant"
    else:
        model = "llama-3.3-70b-versatile"
    max_retries = 3
    retry_delays = [10, 20, 30]  # seconds between retries
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


def render_massing_strategy_sketches(text, skill_id, output_mode):
    if skill_id != "site-potential--massing-and-shading-strategy":
        return
    if output_mode != "Design implication":
        return

    content = (text or "").lower()
    strategies = [
        {
            "keys": ["step", "terrace"],
            "title": "Stepped / Terraced Massing",
            "note": "Lower the solar-critical edge and use upper setbacks as exposed PV roof planes.",
            "blocks": [(48, 78, 58, 34, 86), (104, 88, 58, 34, 58), (160, 98, 58, 34, 34)],
            "sun": "north taller -> south lower",
        },
        {
            "keys": ["split", "bar"],
            "title": "Split-Bar Massing",
            "note": "Break a bulky block into thinner bars to reduce project-to-project obstruction and expose more facade/roof area.",
            "blocks": [(46, 96, 62, 34, 64), (166, 96, 62, 34, 64)],
            "sun": "gap for light ->",
        },
        {
            "keys": ["courtyard", "void", "carve", "subtractive"],
            "title": "Subtractive / Courtyard Massing",
            "note": "Start from the allowed volume, then carve a void where it improves solar and daylight access.",
            "blocks": [(46, 76, 48, 30, 58), (94, 76, 48, 30, 58), (142, 76, 48, 30, 58), (46, 126, 48, 30, 58), (142, 126, 48, 30, 58)],
            "sun": "carved void ->",
        },
        {
            "keys": ["setback", "spacing", "distance"],
            "title": "Increase Setback",
            "note": "Open distance from a tall obstruction before treating the shaded facade as a main PV surface.",
            "blocks": [(50, 90, 56, 34, 88), (178, 104, 60, 34, 48)],
            "gap": True,
            "sun": "setback ->",
        },
        {
            "keys": ["north", "shift height", "shift the height", "dense program"],
            "title": "Shift Height Northward",
            "note": "Keep taller program volume away from the solar-critical south edge.",
            "blocks": [(66, 104, 62, 34, 34), (150, 84, 62, 34, 88)],
            "sun": "lower south edge ->",
        },
        {
            "keys": ["stilt", "lift"],
            "title": "Lifted / Stilted Massing",
            "note": "Lift part of the volume to reduce ground-level obstruction and improve porosity/daylight.",
            "blocks": [(74, 72, 124, 40, 42)],
            "stilts": True,
            "sun": "open ground ->",
        },
    ]

    selected = []
    for strategy in strategies:
        if any(key in content for key in strategy["keys"]):
            selected.append(strategy)
    if not selected:
        return
    selected = selected[:3]

    def cuboid_svg(block):
        x, y, w, d, h = block
        skew = d * 0.5
        a = (x, y)
        b = (x + w, y - skew)
        c = (x + w + d, y)
        dpt = (x + d, y + skew)
        a2 = (a[0], a[1] + h)
        b2 = (b[0], b[1] + h)
        c2 = (c[0], c[1] + h)
        d2 = (dpt[0], dpt[1] + h)

        def pts(*items):
            return " ".join(f"{px:.1f},{py:.1f}" for px, py in items)

        return f"""
          <polygon points="{pts(a, b, c, dpt)}" fill="#d8bf84" stroke="rgba(45,49,66,.24)" stroke-width="1"/>
          <polygon points="{pts(dpt, c, c2, d2)}" fill="#8fbf9f" stroke="rgba(45,49,66,.22)" stroke-width="1"/>
          <polygon points="{pts(a, dpt, d2, a2)}" fill="#b9a06b" stroke="rgba(45,49,66,.22)" stroke-width="1"/>
          <polygon points="{pts(a, b, b2, a2)}" fill="#c6ad75" stroke="rgba(45,49,66,.16)" stroke-width="1"/>
        """

    cards = []
    for strategy in selected:
        blocks = "".join(cuboid_svg(b) for b in strategy["blocks"])
        stilts = ""
        if strategy.get("stilts"):
            stilts = """
              <line x1="92" y1="126" x2="92" y2="176" stroke="#2d3142" stroke-width="5"/>
              <line x1="192" y1="102" x2="192" y2="152" stroke="#2d3142" stroke-width="5"/>
            """
        gap = ""
        if strategy.get("gap"):
            gap = """
              <line x1="118" y1="156" x2="174" y2="156" stroke="#2d3142" stroke-width="1.6" stroke-dasharray="4 4"/>
              <path d="M118 156 l8 -5 m-8 5 l8 5 M174 156 l-8 -5 m8 5 l-8 5" stroke="#2d3142" stroke-width="1.6" fill="none"/>
              <text x="132" y="148" font-size="10" fill="#5f6675">gap</text>
            """
        cards.append(f"""
        <section class="sketch-card">
          <div class="sketch-title">{strategy['title']}</div>
          <div class="scene-wrap">
            <div class="sun-arrow">{strategy['sun']}</div>
            <svg class="massing-svg" viewBox="0 0 300 220" role="img" aria-label="{strategy['title']} schematic">
              {blocks}
              {stilts}
              {gap}
            </svg>
          </div>
          <div class="sketch-note">{strategy['note']}</div>
        </section>
        """)

    html = f"""
    <style>
      .sketch-grid {{
        display:grid;
        grid-template-columns:repeat({len(cards)}, minmax(0, 1fr));
        gap:14px;
        margin:8px 0 18px 0;
        font-family:Inter, -apple-system, BlinkMacSystemFont, sans-serif;
      }}
      .sketch-card {{
        border:1px solid #e0dcd4;
        background:#fffdf8;
        border-radius:8px;
        padding:12px 12px 10px 12px;
        min-height:285px;
      }}
      .sketch-title {{
        color:#2d3142;
        font-size:14px;
        font-weight:650;
        margin-bottom:4px;
      }}
      .scene-wrap {{
        height:205px;
        position:relative;
        overflow:visible;
      }}
      .sun-arrow {{
        position:absolute;
        left:6px;
        top:10px;
        color:#c8a96e;
        font-size:11px;
        font-weight:650;
        text-transform:uppercase;
        letter-spacing:.04em;
      }}
      .massing-svg {{
        position:absolute;
        left:50%;
        top:28px;
        transform:translateX(-50%);
        width:100%;
        max-width:330px;
        height:190px;
      }}
      .sketch-note {{
        color:#5f6675;
        font-size:12px;
        line-height:1.35;
      }}
      @media (max-width: 760px) {{
        .sketch-grid {{ grid-template-columns:1fr; }}
      }}
    </style>
    <div class="sketch-grid">{''.join(cards)}</div>
    """
    components.html(html, height=350 if len(cards) <= 3 else 680, scrolling=False)


def build_system_prompt(skill_md, cea_summary, output_mode, scale, selected_buildings=None, skill_id=None, cea_data=None):
    building_context = ""
    if selected_buildings:
        building_context = f"\nFocus your analysis specifically on: {', '.join(selected_buildings)}."

    mode_instructions = {
        "Key takeaway": """OUTPUT MODE: Key takeaway
Answer the core question of this analysis in the simplest, most understandable way possible.
- 2-3 bullet points maximum.
- Lead with the single most important finding and its number.
- Explain in plain language what that number means — no jargon without explanation.
- End with one concrete "For BIPV," action with a real number.
- No methodology, no context, no benchmarks — just the answer.""",

        "Explain the numbers": """OUTPUT MODE: Explain the numbers
The full analytical breakdown. Cover all of the following:
- What each key number is and where it comes from.
- What it means in context — compare to benchmarks, thresholds, or industry norms where relevant.
- How the numbers relate to each other (e.g. generation vs demand, embodied vs operational carbon).
- Use bullet points, one point per number or comparison.
- Include the actual values — do not be vague.
- This mode is paired with charts generated by the app — do not describe charts, but you may reference what the architect should look for in them.""",

        "Design implication": """OUTPUT MODE: Design implication
A practical recipe for the architect based on the results. No charts.
- 3-5 bullet points, each a specific, actionable design suggestion.
- Every bullet must follow directly from the data — no generic advice.
- Include numbers where they sharpen the recommendation (e.g. area, ratio, orientation).
- Frame each point as: what to do, and why the data supports it.
- Do not explain what the numbers are — assume the architect has already read them."""
    }

    mode_block = mode_instructions.get(output_mode, f"Output mode: {output_mode}")

    compact_metrics = None
    if skill_id in COMPACT_SKILL_TASKS and cea_data is not None:
        compact_metrics = compute_compact_metrics(
            skill_id,
            cea_data,
            selected_buildings=selected_buildings,
            scale=scale,
        )

    if compact_metrics:
        return f"""You are a BIPV expert helping architects interpret CEA4 simulation results.
Scale: {scale}{building_context}

{mode_block}

## Skill task
{COMPACT_SKILL_TASKS[skill_id]}

## Computed metrics
{compact_metrics}

Use only the computed metrics above. Do not invent missing values, sources, tariffs, regulations, or file contents. If a value is unavailable, say so briefly and explain the limitation.
Do NOT describe, mention, or suggest visualizations or charts — these are generated automatically by the app.
Do NOT use markdown headers (#) or numbered lists. You MAY use **bold** sparingly for key numbers and surface names."""

    return f"""You are a BIPV expert helping architects interpret CEA4 simulation results.
Scale: {scale}{building_context}

{mode_block}

## Skill specification
{skill_md[:2000]}

## CEA data
{cea_summary[:3000]}

Use actual numbers from the data where available. If a specific value is missing, note it briefly in one sentence, then proceed using industry-standard defaults clearly labelled as estimates — e.g. grid emissions ~0.4 kgCO₂/kWh for Central Europe, panel cost ~250 €/m², system lifetime 25 years, performance ratio 0.75.
Do NOT describe, mention, or suggest visualizations or charts — these are generated automatically by the app.
Do NOT use markdown headers (#) or numbered lists. You MAY use **bold** sparingly for key numbers and surface names."""


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
                    selected_label = "No buildings selected yet" if n == 0 else f"{n} building{'s' if n > 1 else ''} selected"
                    st.markdown(
                        f'<div class="cluster-counter">{selected_label}</div>',
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
                GOAL_TOOLTIPS = {
                    "Site Potential": "Can this site support solar integration?",
                    "Performance Estimation": "What does the system deliver?",
                    "Impact and Viability": "Is this strategy worth integrating?",
                    "Optimize My Design": "How should I design the building for BIPV?",
                }
                for goal in TREE.keys():
                    label = goal.replace("Impact and Viability", "Impact & Viability")
                    tooltip = GOAL_TOOLTIPS.get(goal, "")
                    if st.button(label, key=f"goal_{goal}", help=tooltip):
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
                TOPIC_TOOLTIPS = {
                    # Site Potential topics
                    "Solar Availability": "Where and when is solar energy available on this site?",
                    "Envelope Suitability": "Which parts of the building envelope are suitable for solar integration?",
                    "Massing & Shading Strategy": "How should the building form be shaped to maximize solar access?",
                    "Contextual Feasibility": "Does the surrounding context support or limit solar integration?",
                    # Performance Estimation topics
                    "Energy Generation": "How much energy can this system generate?",
                    "Self Sufficiency": "To what extent can this building cover its own energy demand?",
                    # Impact and Viability topics
                    "Carbon Impact": "How does this design affect lifecycle carbon emissions?",
                    "Economic Viability": "Does this design make financial sense over its lifetime?",
                    # Optimize My Design topics
                    "Panel Type Trade-off": "Which panel type makes the most sense for this design?",
                    "Surface Prioritisation": "Where should I place the panels?",
                    "Envelope Simplification": "What small geometric changes would improve performance?",
                    "Construction & Integration": "How can this be integrated into the building?",
                }
                for topic, node in topics.items():
                    topic_tooltip = TOPIC_TOOLTIPS.get(topic, "")
                    if st.button(topic, key=f"sub_{topic}", help=topic_tooltip):
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
                    ANALYSIS_TOOLTIPS = {
                        "Surface Irradiation": "Where is solar energy available on this site?",
                        "Temporal Availability": "When is solar energy available on this site?",
                        "Infrastructure Readiness": "Is the necessary infrastructure in place to support solar integration?",
                        "Regulatory Constraints": "What legal constraints shape how solar systems can be integrated here?",
                        "Basic Economic Signal": "Is solar integration likely to be financially worthwhile here?",
                        "Operational Carbon Footprint": "How much carbon will this building emit during operation?",
                        "Carbon Payback Period": "When does this design pay back its embodied carbon?",
                        "Cost Analysis": "Is BIPV-generated electricity cost-competitive with grid electricity?",
                        "Investment Payback": "How long until the system recovers its initial investment?",
                    }
                    for child, child_node in node["children"].items():
                        child_tooltip = ANALYSIS_TOOLTIPS.get(child, "")
                        if st.button(child, key=f"subsub_{child}", help=child_tooltip):
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
                    SUBANALYSIS_TOOLTIPS = {
                        "Seasonal Patterns": "How does solar availability change across the seasons?",
                        "Daily Patterns": "How does solar availability vary across a typical day?",
                        "Storage Necessity": "Does the project need short-term or seasonal storage, and what does that mean for BIPV design?",
                    }
                    for grandchild, grandchild_node in child_node["children"].items():
                        grandchild_tooltip = SUBANALYSIS_TOOLTIPS.get(grandchild, "")
                        if st.button(grandchild, key=f"subsubsub_{grandchild}", help=grandchild_tooltip):
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
                selected_buildings=selected_buildings,
                skill_id=st.session_state.skill_id,
                cea_data=st.session_state.cea_data
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
                if i == 1:
                    render_massing_strategy_sketches(
                        msg["content"],
                        st.session_state.skill_id,
                        st.session_state.get("tree_mode")
                    )
                # Render chart inline after first AI response only
                if (i == 1
                        and st.session_state.skill_id
                        and st.session_state.cea_data
                        and st.session_state.get("tree_mode") == "Explain the numbers"):
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
                            "Explain the numbers"
                        )
                        if _chart is not None:
                            st.altair_chart(_chart, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Chart could not render: {e}")

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

