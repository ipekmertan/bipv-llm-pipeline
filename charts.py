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
import re
import html
from pathlib import Path
from urllib.parse import quote_plus, urlparse, parse_qs, unquote
import requests
import sys
sys.path.append(str(Path(__file__).parent / "scripts"))
from threshold_module import get_threshold_check, THRESHOLD_RELEVANT_SKILLS, parse_epw_location

# Map each skill to the simulations whose parameters need checking
SKILL_SIMULATION_MAP = {
    "site-potential--solar-availability--surface-irradiation": ["solar_irradiation"],
    "site-potential--solar-availability--temporal-availability--seasonal-patterns": ["solar_irradiation"],
    "site-potential--solar-availability--temporal-availability--daily-patterns": ["solar_irradiation"],
    "site-potential--solar-availability--temporal-availability--storage-strategy": ["solar_irradiation", "pv", "demand"],
    "site-potential--envelope-suitability": ["solar_irradiation"],
    "site-potential--massing-and-shading-strategy": ["solar_irradiation"],
    "performance-estimation--energy-generation": ["pv"],
    "performance-estimation--panel-type-tradeoff": ["pv"],
    "optimize-my-design--panel-type-tradeoff": ["pv"],
    "optimize-my-design--surface-prioritization": ["pv"],
    "optimize-my-design--envelope-simplification": ["pv"],
    "optimize-my-design--construction-and-integration": ["pv"],
    "optimize-my-design--design-integration-recipe": ["solar_irradiation", "pv", "demand"],
    "optimize-my-design--pv-coverage-scenario": ["pv", "demand"],
    "performance-estimation--self-sufficiency": ["pv", "demand"],
    "impact-and-viability--carbon-impact--carbon-footprint": ["pv", "demand"],
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
INFRASTRUCTURE_CONTEXT_PATH = Path(__file__).parent / "configuration" / "infrastructure_context.json"
REGULATORY_CONTEXT_PATH = Path(__file__).parent / "configuration" / "regulatory_context.json"
ECONOMIC_CONTEXT_PATH = Path(__file__).parent / "configuration" / "economic_context.json"

SKILL_FOLDER_ALIASES = {
    "impact-and-viability--carbon-impact--carbon-footprint": [
        "impact-and-viability--carbon-impact--operational-carbon-footprint",
    ],
    "impact-and-viability--carbon-impact--operational-carbon-footprint": [
        "impact-and-viability--carbon-impact--carbon-footprint",
    ],
    "performance-estimation--panel-type-tradeoff": [
        "optimize-my-design--panel-type-tradeoff",
    ],
    "optimize-my-design--panel-type-tradeoff": [
        "performance-estimation--panel-type-tradeoff",
    ],
}

SINGLE_OUTPUT_SKILLS = {
    "site-potential--contextual-feasibility--regulatory-constraints": "Regulatory brief",
    "optimize-my-design--design-integration-recipe": "Design recipe",
    "optimize-my-design--pv-coverage-scenario": "Coverage scenario",
}

@st.cache_data
def load_skills_index():
    with open(SKILLS_INDEX_PATH) as f:
        return json.load(f)["skills"]

@st.cache_data
def load_infrastructure_context():
    if not INFRASTRUCTURE_CONTEXT_PATH.exists():
        return {}
    with open(INFRASTRUCTURE_CONTEXT_PATH) as f:
        return json.load(f)

@st.cache_data
def load_regulatory_context():
    if not REGULATORY_CONTEXT_PATH.exists():
        return {}
    with open(REGULATORY_CONTEXT_PATH) as f:
        return json.load(f)

@st.cache_data
def load_economic_context():
    if not ECONOMIC_CONTEXT_PATH.exists():
        return {}
    with open(ECONOMIC_CONTEXT_PATH) as f:
        return json.load(f)

@st.cache_data(ttl=3600)
def load_acacia_curves():
    local = Path(__file__).parent / "scripts" / "static_curve_data.json"
    with open(local) as f:
        return json.load(f)

def load_skill_md(skill_id):
    candidate_names = [skill_id] + SKILL_FOLDER_ALIASES.get(skill_id, [])
    for folder in SKILLS_DIR.iterdir():
        if folder.name.strip() in candidate_names:
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


def _polygon_area_and_perimeter(points):
    if len(points) < 3:
        return 0.0, 0.0
    area = 0.0
    perimeter = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
        perimeter += math.hypot(x2 - x1, y2 - y1)
    return abs(area) / 2.0, perimeter


def _read_shp_geometry_metrics(shp_path):
    metrics = []
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
                    bbox_area = max(0, (maxx - minx) * (maxy - miny))
                    area = None
                    perimeter = None
                    if shape_type == 5 and len(content) >= 44:
                        try:
                            num_parts, num_points = struct.unpack("<2i", content[36:44])
                            parts_start = 44
                            points_start = parts_start + 4 * num_parts
                            parts = list(struct.unpack(f"<{num_parts}i", content[parts_start:points_start]))
                            points = [
                                struct.unpack("<2d", content[points_start + i * 16:points_start + (i + 1) * 16])
                                for i in range(num_points)
                            ]
                            part_areas = []
                            part_perimeters = []
                            for part_idx, start in enumerate(parts):
                                end = parts[part_idx + 1] if part_idx + 1 < len(parts) else len(points)
                                ring_area, ring_perimeter = _polygon_area_and_perimeter(points[start:end])
                                part_areas.append(ring_area)
                                part_perimeters.append(ring_perimeter)
                            if part_areas:
                                area = sum(part_areas)
                                perimeter = sum(part_perimeters)
                        except Exception:
                            area = None
                            perimeter = None
                    metrics.append({
                        "minx": minx,
                        "miny": miny,
                        "maxx": maxx,
                        "maxy": maxy,
                        "bbox_width_m": max(0, maxx - minx),
                        "bbox_depth_m": max(0, maxy - miny),
                        "centroid_x": (minx + maxx) / 2,
                        "centroid_y": (miny + maxy) / 2,
                        "footprint_m2": area if area is not None and area > 0 else bbox_area,
                        "footprint_bbox_m2": bbox_area,
                        "footprint_perimeter_m": perimeter,
                    })
                else:
                    metrics.append({})
    except Exception:
        return []
    return metrics


def _read_geometry_table(shp_path):
    dbf_path = shp_path.with_suffix(".dbf")
    records = _read_dbf_records(dbf_path)
    bboxes = _read_shp_geometry_metrics(shp_path)
    rows = []
    for idx, record in enumerate(records):
        row = dict(record)
        if idx < len(bboxes):
            row.update(bboxes[idx])
        rows.append(row)
    return pd.DataFrame(rows) if rows else None


def _annual_ghi_from_epw(epw_path):
    """Return annual global horizontal irradiation from EPW in kWh/m2/year."""
    total_wh_m2 = 0.0
    count = 0
    try:
        with open(epw_path, "r", errors="ignore") as f:
            for line_no, line in enumerate(f):
                if line_no < 8:
                    continue
                parts = line.strip().split(",")
                if len(parts) <= 13:
                    continue
                try:
                    ghi = float(parts[13])
                except (TypeError, ValueError):
                    continue
                if ghi >= 0:
                    total_wh_m2 += ghi
                    count += 1
    except Exception:
        return None
    return round(total_wh_m2 / 1000, 1) if count else None


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

        solar_radiation_dir = scenario / "outputs" / "data" / "solar-radiation"
        if solar_radiation_dir.exists():
            for fpath in sorted(solar_radiation_dir.glob("*_radiation.csv")):
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
                annual_ghi = _annual_ghi_from_epw(epw)
                if annual_ghi is not None:
                    result["files"]["weather_annual_ghi_kwh_m2"] = annual_ghi
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
        "Combine CEA project pressure with any supplied public utility/grid context to turn infrastructure "
        "constraints into early BIPV design choices: PV ambition, staging, self-consumption, electrical-room "
        "allowance, risers, metering/switchgear space, storage readiness, and thermal-system narrative. "
        "If precise utility data is missing, keep the main answer useful and add only a short precision note "
        "saying who to contact and exactly what to ask."
    ),
    "performance-estimation--energy-generation": (
        "Interpret the PV generation result for the selected analysis scope. Focus on total annual generation, "
        "peak generation, generation intensity, strongest/weakest month, average daily generation window, and "
        "roof/facade contribution to total PV output. Do not reuse district totals for selected buildings or clusters. "
        "Do not repeat Solar Irradiation's placement ranking except where it explains the total generation result."
    ),
    "performance-estimation--self-sufficiency": (
        "Interpret how much of the selected scope's electricity demand is covered by BIPV. Focus on direct hourly "
        "self-sufficiency, annual PV coverage before timing losses, self-consumption, exported surplus, grid import, "
        "monthly dependency, and daily mismatch. Use selected building/cluster demand files when supplied; never use "
        "district totals or irradiation values as the selected building result."
    ),
    "impact-and-viability--carbon-impact--carbon-footprint": (
        "Interpret the selected scope's annual electricity-carbon footprint and how much BIPV reduces it. Focus on "
        "baseline grid-electricity carbon, hourly PV used on site, BIPV avoided carbon, net electricity carbon after "
        "BIPV, and annual reduction percentage. Do not discuss panel manufacturing carbon or carbon payback years."
    ),
    "impact-and-viability--carbon-impact--operational-carbon-footprint": (
        "Interpret the selected scope's annual electricity-carbon footprint and how much BIPV reduces it. Focus on "
        "baseline grid-electricity carbon, hourly PV used on site, BIPV avoided carbon, net electricity carbon after "
        "BIPV, and annual reduction percentage. Do not discuss panel manufacturing carbon or carbon payback years."
    ),
    "impact-and-viability--carbon-impact--carbon-payback": (
        "Interpret the selected scope's carbon payback period: active PV area, embodied panel carbon, annual avoided "
        "carbon, and years until avoided operational carbon offsets panel manufacturing carbon. Respect the selected "
        "scale and do not use district totals for building/cluster results."
    ),
    "impact-and-viability--economic-viability--cost-analysis": (
        "Interpret the selected scope's BIPV cost screen: active roof/facade PV area, estimated investment, annual "
        "electricity value, and cost competitiveness. Respect the selected scale and use the project-specific screen."
    ),
    "impact-and-viability--economic-viability--investment-payback": (
        "Interpret the selected scope's BIPV payback screen: estimated investment, annual value, simple payback, and "
        "25-year return direction. Respect the selected scale and use the project-specific screen."
    ),
    "site-potential--contextual-feasibility--regulatory-constraints": (
        "Combine the project location with supplied public planning/regulatory context to turn BIPV rules into "
        "early design choices: whether roof/facade BIPV is likely straightforward, restricted, mandatory, "
        "heritage-sensitive, documentation-heavy, or timeline-sensitive. If precise local planning status is "
        "missing, keep the main answer useful and add a short precision note saying which authority to contact "
        "and exactly what to ask."
    ),
    "site-potential--contextual-feasibility--basic-economic-signal": (
        "Combine the project location with supplied public market/economic context to identify the strongest "
        "early BIPV argument: electricity-cost savings, carbon reduction, regulation/compliance, architectural "
        "value, or resilience. Use prices, grid carbon, export compensation, cost ranges, and payback ranges "
        "only when supplied; otherwise give a useful concept-level framing and a short precision note."
    ),
    "performance-estimation--panel-type-tradeoff": (
        "Interpret the simulated PV panel type comparison using actual generation, installed area, yield "
        "per square metre, and panel database values where available. Avoid assuming one technology is best "
        "unless the metrics show it."
    ),
    "optimize-my-design--panel-type-tradeoff": (
        "Interpret the simulated PV panel type comparison using actual generation, installed area, yield "
        "per square metre, and panel database values where available. Avoid assuming one technology is best "
        "unless the metrics show it."
    ),
    "optimize-my-design--design-integration-recipe": (
        "Create one consolidated BIPV design recipe from the analyses already run in this session and the current "
        "project metrics. Prioritise design decisions: where PV goes, how much active area to use or keep PV-ready, "
        "which surfaces to skip, what panel/envelope strategy to prefer, what storage/grid/equipment space to allow, "
        "what client argument is strongest, and what the architect should do next. Do not repeat every prior analysis."
    ),
    "optimize-my-design--pv-coverage-scenario": (
        "This is a local scenario tool, not an LLM interpretation. It lets the architect test how cost, carbon, "
        "self-sufficiency, export, and active PV area change when only 0-100% of the recommended PV area is used."
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


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _monthly_from_hourly(df, col):
    date_col = _find_metric_col(df, "date", "time")
    if df is None or col is None or date_col is None:
        return None
    try:
        work = df.copy()
        work["_dt"] = pd.to_datetime(work[date_col], utc=True, errors="coerce")
        work["_month"] = work["_dt"].dt.month
        monthly = pd.to_numeric(work[col], errors="coerce").fillna(0).groupby(work["_month"]).sum() / 1000
        return monthly.reindex(range(1, 13), fill_value=0)
    except Exception:
        return None


def compute_daily_pattern_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    df = None
    source = None
    using_native_building_hourly = False
    if selected_buildings:
        radiation_frames = []
        for building in selected_buildings:
            radiation_df = files.get(f"{building}_radiation.csv")
            if radiation_df is not None:
                radiation_frames.append(radiation_df.copy())
        if radiation_frames:
            df = radiation_frames[0]
            for extra in radiation_frames[1:]:
                time_col = _find_metric_col(df, "date", "time")
                extra_time_col = _find_metric_col(extra, "date", "time")
                if time_col and extra_time_col and len(extra) == len(df):
                    for col in _surface_columns(extra).values():
                        if col and col in extra.columns:
                            if col not in df.columns:
                                df[col] = 0
                            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) + pd.to_numeric(extra[col], errors="coerce").fillna(0)
            source = ", ".join(f"{building}_radiation.csv" for building in selected_buildings if files.get(f"{building}_radiation.csv") is not None)
            using_native_building_hourly = True

    if df is None:
        df = files.get("solar_irradiation_hourly.csv")
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

    selected_surface_totals = {}
    annual_source = None
    if selected_buildings and not using_native_building_hourly:
        annual_df = cea_data["files"].get("solar_irradiation_annually_buildings.csv")
        name_col = _find_metric_col(annual_df, "name", "building") if annual_df is not None else None
        if annual_df is not None and name_col:
            selected_annual = annual_df[annual_df[name_col].isin(selected_buildings)].copy()
            annual_surfaces = {name: col for name, col in _surface_columns(selected_annual).items() if col}
            for surface, annual_col in annual_surfaces.items():
                selected_surface_totals[surface] = float(pd.to_numeric(selected_annual[annual_col], errors="coerce").fillna(0).sum())
            if selected_surface_totals:
                annual_source = "solar_irradiation_annually_buildings.csv"

    lines = [f"Source: {source}"]
    if selected_buildings:
        lines.append(f"Scale: {scale}; selected buildings: {', '.join(selected_buildings)}.")
    if using_native_building_hourly:
        lines.append("Metric: native building-level average 24-hour solar radiation profile from CEA solar-radiation outputs. Hourly kW values are treated as kWh per one-hour timestep.")
    elif annual_source:
        lines.append(
            "Metric: average 24-hour irradiation profile scaled to the selected building annual surface totals. "
            "CEA provides the hourly profile at scenario level here, so this is a building-scaled estimate, not a native building-hourly file."
        )
    else:
        lines.append("Metric: average hourly irradiation by hour of day (0-23), averaged across the year.")

    for surface, col in surfaces.items():
        values = pd.to_numeric(df[col], errors="coerce").fillna(0)
        if surface in selected_surface_totals:
            scenario_annual = float(values.sum())
            if scenario_annual > 0:
                values = values * (selected_surface_totals[surface] / scenario_annual)
        hourly = values.groupby(df["_hour"]).mean().reindex(range(24), fill_value=0)
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


def compute_building_surface_area_values(cea_data, selected_buildings=None):
    """Approximate physical roof/facade areas from zone geometry and WWR."""
    files = cea_data.get("files", {})
    zone_df = files.get("zone_geometry.csv")
    if zone_df is None or zone_df.empty:
        return None

    zone = zone_df.copy()
    name_col = _find_metric_col(zone, "name", "building")
    if selected_buildings and name_col:
        zone = zone[zone[name_col].isin(selected_buildings)]
    if zone.empty:
        return None

    envelope = files.get("envelope.csv")
    if envelope is not None:
        envelope = envelope.copy()
        env_name_col = _find_metric_col(envelope, "name", "building")
        if selected_buildings and env_name_col:
            envelope = envelope[envelope[env_name_col].isin(selected_buildings)]

    def avg_wwr(col):
        if envelope is None or col not in envelope.columns:
            return None
        vals = pd.to_numeric(envelope[col], errors="coerce").dropna()
        return float(vals.mean()) if len(vals) else None

    wwr = {
        "south": avg_wwr("wwr_south"),
        "east": avg_wwr("wwr_east"),
        "west": avg_wwr("wwr_west"),
        "north": avg_wwr("wwr_north"),
    }

    height_col = _height_col(zone)
    roof_area = facade_gross_fallback = 0.0
    south_gross = east_gross = west_gross = north_gross = 0.0

    for _, row in zone.iterrows():
        h = _height_value(row, height_col) or 0.0
        roof_area += float(row.get("footprint_m2", 0) or 0)
        width = float(row.get("bbox_width_m", 0) or 0)
        depth = float(row.get("bbox_depth_m", 0) or 0)
        if width > 0 and depth > 0 and h > 0:
            south_gross += width * h
            north_gross += width * h
            east_gross += depth * h
            west_gross += depth * h
        else:
            perimeter = float(row.get("footprint_perimeter_m", 0) or 0)
            facade_gross_fallback += perimeter * h

    directional = {
        "South facade": (south_gross, wwr["south"]),
        "East facade": (east_gross, wwr["east"]),
        "West facade": (west_gross, wwr["west"]),
        "North facade": (north_gross, wwr["north"]),
    }
    directional_total = sum(gross for gross, _ in directional.values())
    facade_gross = directional_total if directional_total > 0 else facade_gross_fallback
    facade_opaque = sum(
        gross * (1 - ratio) if ratio is not None else gross
        for gross, ratio in directional.values()
    ) if directional_total > 0 else facade_gross_fallback

    return {
        "roof_area_m2": roof_area,
        "facade_gross_m2": facade_gross,
        "facade_opaque_m2": facade_opaque,
        "directional_facades": directional,
    }


def compute_active_pv_area_values(cea_data, selected_buildings=None):
    """Read CEA's simulated active module area from PV result files."""
    files = cea_data.get("files", {})
    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total_buildings.csv")), None)
    if not pv_fname:
        return None

    df = files.get(pv_fname)
    if df is None or df.empty:
        return None
    df = df.copy()
    name_col = _find_metric_col(df, "name", "building")
    if selected_buildings and name_col:
        df = df[df[name_col].isin(selected_buildings)]
    if df.empty:
        return None

    def sum_col(col):
        if col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())

    roof = sum_col("PV_roofs_top_m2")
    facades = {
        "South facade": sum_col("PV_walls_south_m2"),
        "East facade": sum_col("PV_walls_east_m2"),
        "West facade": sum_col("PV_walls_west_m2"),
        "North facade": sum_col("PV_walls_north_m2"),
    }
    facade_total = sum(facades.values())
    total_col = _find_metric_col(df, "area_PV_m2", "Area_PV")
    total = sum_col(total_col) if total_col else roof + facade_total
    if total <= 0:
        total = roof + facade_total

    return {
        "source": pv_fname,
        "roof_m2": roof,
        "facade_m2": facade_total,
        "total_m2": total,
        "directional_facades": facades,
    }


def compute_building_surface_area_screen(cea_data, selected_buildings=None):
    values = compute_building_surface_area_values(cea_data, selected_buildings)
    if not values:
        return []
    active = compute_active_pv_area_values(cea_data, selected_buildings)

    rows = [f"- Approximate physical roof footprint: {_format_number(values['roof_area_m2'], ' m2', 1)}."]
    facade_gross = values["facade_gross_m2"]
    facade_opaque = values["facade_opaque_m2"]
    directional = values["directional_facades"]
    if facade_gross > 0:
        rows.append(f"- Approximate gross facade area: {_format_number(facade_gross, ' m2', 1)}.")
        rows.append(f"- Approximate opaque facade area after WWR: {_format_number(facade_opaque, ' m2', 1)}.")
        for label, (gross, ratio) in directional.items():
            if gross > 0:
                opaque = gross * (1 - ratio) if ratio is not None else gross
                ratio_text = _format_number(ratio * 100, '% WWR', 0) if ratio is not None else "WWR not available"
                rows.append(f"- {label}: gross {_format_number(gross, ' m2', 1)}; opaque {_format_number(opaque, ' m2', 1)} ({ratio_text}).")
    if active:
        roof_ratio = active["roof_m2"] / values["roof_area_m2"] * 100 if values["roof_area_m2"] > 0 else None
        facade_ratio = active["facade_m2"] / facade_opaque * 100 if facade_opaque > 0 else None
        rows.append(
            f"- CEA simulated active PV module area: roof {_format_number(active['roof_m2'], ' m2', 1)} "
            f"({_format_number(roof_ratio, '% of physical roof footprint', 1)}); facade "
            f"{_format_number(active['facade_m2'], ' m2', 1)} "
            f"({_format_number(facade_ratio, '% of approximate opaque facade area', 1)})."
        )
    rows.append("Area note: physical roof/facade areas are geometry-based approximations from zone.shp plus envelope WWR. CEA PV area is simulated active module area after radiation threshold, panel spacing, and PV placement filters; it is not the same as fully covering every roof/facade square metre.")
    return rows


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
    pv_source = pv_fname or "no PV total file"
    pv_peak_note = "from hourly PV total file"

    selected_annual_pv_kwh = None
    if selected_buildings and pv_fname:
        pv_buildings_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
        pv_buildings_df = files.get(pv_buildings_fname)
        if pv_buildings_df is not None:
            pv_b_name_col = _find_metric_col(pv_buildings_df, "name", "building")
            pv_b_col = _find_metric_col(pv_buildings_df, "E_PV_gen", "E_PV", "gen")
            if pv_b_name_col and pv_b_col:
                selected_pv_buildings = pv_buildings_df[pv_buildings_df[pv_b_name_col].isin(selected_buildings)]
                if not selected_pv_buildings.empty:
                    selected_annual_pv_kwh = float(selected_pv_buildings[pv_b_col].sum())
                    pv_source = f"{pv_fname} scaled to selected buildings using {pv_buildings_fname}"
                    pv_peak_note = "estimated by scaling district hourly PV profile to selected annual PV generation"

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

    district_annual_pv_kwh = float(pv_df[pv_col].sum()) if pv_df is not None and pv_col else None
    if selected_annual_pv_kwh is not None and district_annual_pv_kwh and district_annual_pv_kwh > 0:
        pv_scale = selected_annual_pv_kwh / district_annual_pv_kwh
        peak_pv_kw = float(pv_df[pv_col].max()) * pv_scale if pv_df is not None and pv_col else None
        annual_pv_kwh = selected_annual_pv_kwh
    else:
        peak_pv_kw = float(pv_df[pv_col].max()) if pv_df is not None and pv_col else None
        annual_pv_kwh = district_annual_pv_kwh
    peak_demand_kw = float(demand_df[demand_col].max()) if demand_df is not None and demand_col else None
    annual_demand_kwh = float(demand_df[demand_col].sum()) if demand_df is not None and demand_col else None

    pv_to_demand_peak = (peak_pv_kw / peak_demand_kw) if peak_pv_kw is not None and peak_demand_kw and peak_demand_kw > 0 else None
    pv_to_demand_annual = (annual_pv_kwh / annual_demand_kwh) if annual_pv_kwh is not None and annual_demand_kwh and annual_demand_kwh > 0 else None
    if pv_to_demand_peak is None:
        export_pressure = "unknown"
    elif pv_to_demand_peak < 0.5:
        export_pressure = "low: PV peak is below half of peak electricity demand"
    elif pv_to_demand_peak <= 1.0:
        export_pressure = "moderate: PV peak is below peak electricity demand, but export may occur during low-load sunny hours"
    else:
        export_pressure = "high: PV peak exceeds peak electricity demand, so self-consumption and export constraints matter"

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

    if pv_to_demand_peak is None:
        concept_stance = "UNKNOWN - the app cannot compare peak PV and peak electricity demand from the extracted files."
        pv_ambition = "keep PV zones flexible until hourly PV and demand data are available."
        concept_design_move = "reserve generic electrical routes and avoid locking the facade/roof strategy to an export-heavy concept."
        design_allowances = "inverter room, vertical risers, accessible roof/facade maintenance zones, and a future battery-ready area if the project later shows export pressure"
    elif pv_to_demand_peak < 0.5:
        concept_stance = "MANAGEABLE - the simulated PV peak is lower than half of the selected load peak, so export pressure is not the main early-design concern."
        pv_ambition = "roof-led or best-surface BIPV can be explored without immediately reducing PV area, while still keeping the grid connection check open."
        concept_design_move = "prioritise the most useful solar surfaces and keep electrical rooms/routes simple but expandable."
        design_allowances = "compact inverter/electrical space, short DC cable routes, roof/facade access, and spare riser capacity for later PV expansion"
    elif pv_to_demand_peak <= 1.0:
        concept_stance = "SELF-CONSUMPTION-FIRST - PV peak is comparable to the selected load peak, so sunny low-load hours may still create export pressure."
        pv_ambition = "use the best roof/facade zones, but shape the concept around matching building loads before assuming unrestricted export."
        concept_design_move = "distribute PV across surfaces/times, reserve space for inverter equipment, and keep a battery-ready or load-shifting option."
        design_allowances = "inverter room, battery-ready space, vertical risers, meter/export connection allowance, and accessible maintenance routes"
    else:
        concept_stance = "EXPORT-SENSITIVE - PV peak exceeds the selected load peak, so the concept should not assume every high-irradiation surface can export freely."
        pv_ambition = "stage the BIPV area, prioritise self-consumed generation, or pair large PV areas with storage/load-shifting before treating maximum generation as the design target."
        concept_design_move = "design PV zones in phases and keep enough service space for storage, power electronics, and utility-side requirements."
        design_allowances = "larger inverter/electrical room, battery or thermal-storage-ready area, clear cable/riser routes, switchgear/metering space, and future curtailment or staged-connection flexibility"

    pv_buildings_for_staging = None
    if pv_fname:
        pv_buildings_for_staging = files.get(pv_fname.replace("_total.csv", "_total_buildings.csv"))
        if pv_buildings_for_staging is not None:
            pv_stage_name_col = _find_metric_col(pv_buildings_for_staging, "name", "building")
            if selected_buildings and pv_stage_name_col:
                pv_buildings_for_staging = pv_buildings_for_staging[
                    pv_buildings_for_staging[pv_stage_name_col].isin(selected_buildings)
                ].copy()

    surface_stage_candidates = []
    surface_columns = [
        ("Roof", ["PV_roofs_top_E_kWh", "PV_roofs_top_m2"], "lowest visual constraint; usually first priority if access and roof program allow it"),
        ("South facade", ["PV_walls_south_E_kWh", "PV_walls_south_m2"], "strong facade candidate; useful as visible architectural BIPV if WWR/opaque area allows it"),
        ("East facade", ["PV_walls_east_E_kWh", "PV_walls_east_m2"], "morning generation; useful when morning loads or east visibility matter"),
        ("West facade", ["PV_walls_west_E_kWh", "PV_walls_west_m2"], "afternoon generation; useful for cooling or late-day loads"),
        ("North facade", ["PV_walls_north_E_kWh", "PV_walls_north_m2"], "usually lower priority unless data shows meaningful yield or design integration value"),
    ]
    if pv_buildings_for_staging is not None and not pv_buildings_for_staging.empty:
        for surface, cols, note in surface_columns:
            gen_col = next((c for c in cols if c in pv_buildings_for_staging.columns and c.endswith("_E_kWh")), None)
            area_col = next((c for c in cols if c in pv_buildings_for_staging.columns and c.endswith("_m2")), None)
            gen = float(pd.to_numeric(pv_buildings_for_staging[gen_col], errors="coerce").sum()) if gen_col else 0.0
            area = float(pd.to_numeric(pv_buildings_for_staging[area_col], errors="coerce").sum()) if area_col else None
            if gen > 0 or (area is not None and area > 0):
                surface_stage_candidates.append({
                    "surface": surface,
                    "generation": gen,
                    "area": area,
                    "yield_m2": gen / area if area and area > 0 else None,
                    "note": note,
                })
    surface_stage_candidates = sorted(
        surface_stage_candidates,
        key=lambda row: (row["generation"], row["yield_m2"] or 0),
        reverse=True
    )

    staging_recommended = (
        pv_to_demand_peak is None
        or pv_to_demand_peak >= 0.5
        or (transformer_ratio is not None and transformer_ratio >= 0.25)
    )

    stage_lines = []
    if not staging_recommended:
        stage_lines.append(
            "- Staged facade PV is not required by the current CEA infrastructure screen. "
            "The PV peak is low enough relative to demand/indicative transformer capacity that the concept can keep the best PV surfaces active from day one, while still leaving normal spare riser capacity for future expansion."
        )
    elif surface_stage_candidates:
        stage_1 = surface_stage_candidates[:1]
        stage_2 = surface_stage_candidates[1:3]
        stage_3 = surface_stage_candidates[3:]

        def stage_text(title, rows, purpose):
            if not rows:
                return None
            bits = []
            for row in rows:
                bits.append(
                    f"{row['surface']} ({_format_number(row['generation'], ' kWh/year')}; "
                    f"area {_format_number(row['area'], ' m2', 1)}; "
                    f"yield {_format_number(row['yield_m2'], ' kWh/m2/year', 1)})"
                )
            return f"- {title}: {', '.join(bits)}. {purpose}"

        stage_lines.append(stage_text("Stage 1 / must-keep PV zone", stage_1, "Connect this first because it gives the strongest simulated PV contribution."))
        stage_lines.append(stage_text("Stage 2 / expansion PV zone", stage_2, "Keep these zones PV-ready and connect if export capacity, budget, and facade design allow it."))
        stage_lines.append(stage_text("Stage 3 / optional or cladding-compatible zone", stage_3, "Use as future PV, inactive PV-ready cladding, or visually compatible non-PV cladding if grid/export constraints are tight."))
        stage_lines = [line for line in stage_lines if line]
    else:
        stage_lines.append("- Staged PV is recommended, but surface-specific PV staging cannot be calculated because PV surface generation/area columns were not found. Use the irradiation and envelope-suitability outputs to rank roof and facade zones.")

    if peak_pv_kw is None:
        inverter_room_m2 = None
    elif peak_pv_kw <= 30:
        inverter_room_m2 = 4
    elif peak_pv_kw <= 100:
        inverter_room_m2 = 6
    elif peak_pv_kw <= 250:
        inverter_room_m2 = 10
    elif peak_pv_kw <= 500:
        inverter_room_m2 = 16
    else:
        inverter_room_m2 = max(20, math.ceil(peak_pv_kw / 25))

    if pv_to_demand_peak is None or pv_to_demand_peak < 0.5:
        battery_ready_m2 = 0
        battery_ready_note = "battery-ready space is optional at concept stage unless the design intentionally adds resilience or load shifting"
    elif pv_to_demand_peak <= 1.0:
        battery_ready_m2 = max(4, round((peak_pv_kw or 0) / 40))
        battery_ready_note = "reserve a small battery/load-shifting-ready zone because sunny low-load hours may create export pressure"
    else:
        battery_ready_m2 = max(8, round((peak_pv_kw or 0) / 25))
        battery_ready_note = "reserve a larger storage-ready zone because export constraints could affect how much PV can operate at peak"

    service_location_note = (
        "Place the inverter/electrical room next to the main vertical riser between the largest PV zone and the grid/metering room. "
        "For roof-led PV, upper-floor or roof-adjacent plant space reduces DC routing; for facade-led PV, align the riser with the dominant PV elevation and keep maintenance access separated from occupied facade zones."
    )

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
        f"Sources: {pv_source}; {demand_source if demand_df is not None else 'no hourly demand file'}; GRID.csv {'available' if grid_df is not None else 'not available'}; supply.csv {'available' if supply_df is not None else 'not available'}.",
        f"Scale: {scale}",
        f"Project-side infrastructure pressure class from CEA screening: {readiness}.",
        "User-facing rule: the main answer should do the research translation work for the architect. Use CEA for project-side pressure and any supplied public utility/grid facts for context; convert both into early design priorities and selectable options.",
        "If public utility/grid information is supplied, interpret it for early design decisions: PV staging, self-consumption priority, metering/switchgear space, plant-room allowance, storage readiness, and whether export assumptions should shape facade/roof PV area.",
        "If exact transformer capacity, export cap, tariffs, or utility approval rules are missing, do not let the main answer become a caveat. Add a short final precision note only when useful: who to contact and exactly what to ask for.",
        "Concept-phase design guidance:",
        f"- Concept-phase stance: {concept_stance}",
        f"- PV ambition: {pv_ambition}",
        f"- Main design move: {concept_design_move}",
        f"- Reserve now: {design_allowances}.",
        "Grid/export screening:",
    ]
    lines.append(f"- Peak PV generation: {_format_number(peak_pv_kw, ' kW', 1)} ({pv_peak_note}).")
    lines.append(f"- Annual PV generation: {_format_number(annual_pv_kwh, ' kWh/year')}.")
    lines.append(f"- Peak electricity demand: {_format_number(peak_demand_kw, ' kW', 1)}.")
    lines.append(f"- Annual electricity demand: {_format_number(annual_demand_kwh, ' kWh/year')}.")
    lines.append(
        f"- Export-pressure screen: {export_pressure}. "
        f"Estimated PV peak is {_format_number(pv_to_demand_peak * 100 if pv_to_demand_peak is not None else None, '%', 1)} of peak demand."
    )
    lines.append(
        f"- Annual coverage screen: PV generation is {_format_number(pv_to_demand_annual * 100 if pv_to_demand_annual is not None else None, '%', 1)} "
        "of annual electricity demand."
    )
    lines.append(
        f"- Transformer screening: peak PV is {_format_number(transformer_ratio * 100 if transformer_ratio is not None else None, '%', 1)} "
        f"of an indicative {transformer_assumption_kva} kVA neighbourhood transformer. Replace this assumption with actual utility data when available."
    )
    lines.append("Architectural control variables for explaining the numbers:")
    lines.append("- PV peak vs demand peak controls whether the concept can keep maximum PV area, should prioritise self-consumption, or should stage some PV zones until export capacity is confirmed.")
    lines.append("- Annual PV vs annual demand controls whether the BIPV story is partial load support, near-annual matching, or surplus-generation/export-sensitive.")
    lines.append("- Transformer screening is only an early warning; it controls how strongly the design should reserve switchgear/metering/export-connection space before utility data is known.")
    lines.append("- Cable length is not defined by CEA. Do not invent a maximum cable length. Instead, translate it as an architectural requirement: place inverter/electrical rooms within the project-specific allowed route distance from roof/facade PV zones once the electrical design limit is known.")
    lines.append("- The architect controls room location, riser alignment, PV zoning, staged expansion space, maintenance access, and whether storage-ready space is possible.")
    lines.append("Specific concept-stage PV staging guidance from simulated surface PV results:")
    if staging_recommended:
        lines.append("- Meaning of staging: do not design the facade so every PV panel must be installed and connected on day one. Divide BIPV into phases or zones, so the building can keep a coherent facade while the active PV area can respond to export capacity, budget, and utility approval.")
        lines.append("- Stage logic: Stage 1 is the must-keep active PV zone; Stage 2 is PV-ready expansion if grid/export and budget allow; Stage 3 is optional PV-ready cladding or visually compatible non-PV cladding if constraints are tight.")
    lines.extend(stage_lines)
    lines.append("Specific concept-stage equipment-space allowance:")
    lines.append(
        f"- Inverter/electrical room: reserve about {_format_number(inverter_room_m2, ' m2', 0)} "
        "as an early placeholder for PV inverter/electrical equipment. This is a concept allowance, not final electrical design."
    )
    lines.append(
        f"- Battery/load-shifting-ready area: reserve about {_format_number(battery_ready_m2, ' m2', 0)}. "
        f"{battery_ready_note}."
    )
    lines.append(f"- Preferred location: {service_location_note}")

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
    lines.append("- Do not claim or discuss net metering, feed-in tariff, transformer capacity, export cap, or utility approval status unless an external search module supplies that information.")
    lines.append("- If external grid facts are missing, keep the main answer focused on design decisions. A short final precision note is allowed: contact the local distribution grid operator / utility and ask for the point-of-connection export limit, nearest transformer spare capacity, PV connection threshold, metering/switchgear requirements, and application timeline.")
    return "\n".join(lines)


def compute_energy_generation_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total.csv")
                     and "buildings" not in k), None)
    if not pv_fname:
        return "No PV total hourly file is available, so energy generation cannot be calculated reliably."

    pv_df = files.get(pv_fname)
    gen_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None
    if pv_df is None or gen_col is None:
        return f"{pv_fname} is available, but no PV generation column was found."

    district_annual_kwh = float(pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).sum())
    annual_kwh = district_annual_kwh
    pv_scale = 1.0
    scope_source = f"{pv_fname} district hourly total"
    surface_source = None
    area_m2 = None
    surface_rows = []

    bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
    pv_b = files.get(bldg_fname)
    if pv_b is not None:
        name_col = _find_metric_col(pv_b, "name", "building")
        gen_b_col = _find_metric_col(pv_b, "E_PV_gen", "E_PV", "gen")
        pv_scope = pv_b.copy()
        if selected_buildings and name_col:
            pv_scope = pv_scope[pv_scope[name_col].isin(selected_buildings)]
            scope_source = f"{bldg_fname} filtered to selected building(s), with hourly profile scaled from {pv_fname}"
        elif scale in ("Building", "Cluster") and selected_buildings:
            scope_source = f"{pv_fname}; selected building filter could not be applied because no name column was found in {bldg_fname}"

        if gen_b_col and not pv_scope.empty:
            annual_kwh = float(pd.to_numeric(pv_scope[gen_b_col], errors="coerce").fillna(0).sum())
            pv_scale = annual_kwh / district_annual_kwh if district_annual_kwh > 0 else 1.0

        area_cols = [c for c in pv_scope.columns if c.endswith("_m2") and ("PV_roofs" in c or "PV_walls" in c or "area_PV" in c)]
        if area_cols and not pv_scope.empty:
            area_m2 = float(sum(pd.to_numeric(pv_scope[c], errors="coerce").fillna(0).sum() for c in area_cols))

        surface_defs = [
            ("Roof", "PV_roofs_top_E_kWh", "PV_roofs_top_m2"),
            ("South facade", "PV_walls_south_E_kWh", "PV_walls_south_m2"),
            ("East facade", "PV_walls_east_E_kWh", "PV_walls_east_m2"),
            ("West facade", "PV_walls_west_E_kWh", "PV_walls_west_m2"),
            ("North facade", "PV_walls_north_E_kWh", "PV_walls_north_m2"),
        ]
        for surface, e_col, a_col in surface_defs:
            if e_col in pv_scope.columns:
                kwh = float(pd.to_numeric(pv_scope[e_col], errors="coerce").fillna(0).sum())
                sqm = float(pd.to_numeric(pv_scope[a_col], errors="coerce").fillna(0).sum()) if a_col in pv_scope.columns else None
                if kwh > 0 or (sqm is not None and sqm > 0):
                    surface_rows.append((surface, kwh, sqm, kwh / annual_kwh * 100 if annual_kwh > 0 else None))
        if surface_rows:
            surface_source = bldg_fname

    monthly = _monthly_from_hourly(pv_df, gen_col)
    peak_kw = float(pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).max()) * pv_scale
    date_col = _find_metric_col(pv_df, "date", "time")
    peak_hour = None
    meaningful_hours = None
    if date_col:
        pv_hourly = pv_df.copy()
        pv_hourly["_dt"] = pd.to_datetime(pv_hourly[date_col], utc=True, errors="coerce")
        pv_hourly["_hour"] = pv_hourly["_dt"].dt.hour
        hourly_avg = pd.to_numeric(pv_hourly[gen_col], errors="coerce").fillna(0).groupby(pv_hourly["_hour"]).mean() * pv_scale
        if not hourly_avg.empty:
            peak_hour = int(hourly_avg.idxmax())
            max_hourly = float(hourly_avg.max())
            if max_hourly > 0:
                meaningful_hours = [int(h) for h, v in hourly_avg.items() if v >= max_hourly * 0.1]

    lines = [
        f"Source: {scope_source}.",
        f"Scale: {scale}.",
    ]
    if selected_buildings:
        lines.append(f"Selected buildings: {', '.join(selected_buildings)}.")
    lines.append(f"Annual PV generation for this analysis scope: {_format_number(annual_kwh, ' kWh/year')} ({_format_number(annual_kwh / 1000, ' MWh/year', 1)}).")
    if selected_buildings:
        lines.append(f"Important scale rule: do not use the district total of {_format_number(district_annual_kwh, ' kWh/year')} as the selected building/cluster result.")
    lines.append(f"Peak PV generation for this scope: {_format_number(peak_kw, ' kW', 1)}.")
    lines.append(f"CEA simulated active PV module area: {_format_number(area_m2, ' m2', 1)}.")
    if area_m2 and area_m2 > 0:
        lines.append(f"Generation intensity: {_format_number(annual_kwh / area_m2, ' kWh/m2/year', 1)}.")

    if monthly is not None:
        monthly_scaled = monthly * pv_scale
        best_month = int(monthly_scaled.idxmax())
        weakest_month = int(monthly_scaled.idxmin())
        lines.append(
            f"Strongest month: {MONTHS[best_month - 1]} ({_format_number(float(monthly_scaled.loc[best_month]), ' MWh', 1)}). "
            f"Weakest month: {MONTHS[weakest_month - 1]} ({_format_number(float(monthly_scaled.loc[weakest_month]), ' MWh', 1)})."
        )
    if peak_hour is not None:
        if meaningful_hours:
            lines.append(f"Average daily profile: peak generation occurs around {peak_hour}:00; meaningful output is roughly from {min(meaningful_hours)}:00 to {max(meaningful_hours)}:00.")
        else:
            lines.append(f"Average daily profile: peak generation occurs around {peak_hour}:00.")

    if surface_rows:
        lines.append(f"Surface contribution breakdown from {surface_source}:")
        for surface, kwh, sqm, share in sorted(surface_rows, key=lambda r: r[1], reverse=True):
            lines.append(
                f"- {surface}: {_format_number(kwh, ' kWh/year')} "
                f"({_format_number(share, '% of PV generation', 1)}); active area {_format_number(sqm, ' m2', 1)}."
            )
    else:
        lines.append("Surface contribution breakdown was not available from the PV buildings file.")

    lines.append("Interpretation boundary: Energy Generation owns the building-level PV production result. Do not repeat Solar Irradiation's surface-placement ranking except where a surface directly explains the total PV generation.")
    return "\n".join(lines)


def compute_self_sufficiency_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total.csv")
                     and "buildings" not in k), None)
    if not pv_fname:
        return "No PV total hourly file is available, so self-sufficiency cannot be calculated reliably."

    pv_df = files.get(pv_fname)
    gen_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None
    if pv_df is None or gen_col is None:
        return f"{pv_fname} is available, but no PV generation column was found."

    district_annual_pv = float(pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).sum())
    annual_pv = district_annual_pv
    pv_scale = 1.0
    pv_source = f"{pv_fname} district hourly total"

    bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
    pv_b = files.get(bldg_fname)
    if selected_buildings and pv_b is not None:
        name_col = _find_metric_col(pv_b, "name", "building")
        gen_b_col = _find_metric_col(pv_b, "E_PV_gen", "E_PV", "gen")
        if name_col and gen_b_col:
            selected_pv = pv_b[pv_b[name_col].isin(selected_buildings)]
            selected_annual_pv = float(pd.to_numeric(selected_pv[gen_b_col], errors="coerce").fillna(0).sum())
            if selected_annual_pv > 0:
                annual_pv = selected_annual_pv
                pv_scale = annual_pv / district_annual_pv if district_annual_pv > 0 else 1.0
                pv_source = f"{bldg_fname} filtered to selected building(s), with hourly profile scaled from {pv_fname}"

    demand_hourly, demand_source = _sum_hourly_demand_series(files, selected_buildings)
    if demand_hourly is None or len(demand_hourly) == 0:
        return "No hourly electricity demand file was found for the selected scope, so self-sufficiency cannot be calculated reliably."

    pv_hourly = pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).reset_index(drop=True) * pv_scale
    n = min(len(pv_hourly), len(demand_hourly))
    pv_hourly = pv_hourly.iloc[:n].reset_index(drop=True)
    demand_hourly = demand_hourly.iloc[:n].reset_index(drop=True)

    annual_demand = float(demand_hourly.sum())
    annual_pv = float(pv_hourly.sum())
    self_consumed = float(pd.concat([pv_hourly, demand_hourly], axis=1).min(axis=1).sum())
    surplus = float((pv_hourly - demand_hourly).clip(lower=0).sum())
    deficit = float((demand_hourly - pv_hourly).clip(lower=0).sum())
    direct_self_sufficiency = self_consumed / annual_demand * 100 if annual_demand > 0 else None
    annual_coverage = annual_pv / annual_demand * 100 if annual_demand > 0 else None
    self_consumption = self_consumed / annual_pv * 100 if annual_pv > 0 else None

    pv_work = pv_df.iloc[:n].copy()
    date_col = _find_metric_col(pv_work, "date", "time")
    monthly_lines = []
    worst_month = best_month = None
    if date_col:
        pv_work["_dt"] = pd.to_datetime(pv_work[date_col], utc=True, errors="coerce")
        pv_work["_month"] = pv_work["_dt"].dt.month
        pv_work["_pv"] = pv_hourly.values
        pv_work["_demand"] = demand_hourly.values
        pv_work["_self"] = pd.concat([pv_work["_pv"], pv_work["_demand"]], axis=1).min(axis=1)
        monthly = pv_work.groupby("_month")[["_pv", "_demand", "_self"]].sum().reindex(range(1, 13), fill_value=0)
        monthly["_direct_ss"] = monthly.apply(
            lambda r: (r["_self"] / r["_demand"] * 100) if r["_demand"] > 0 else None,
            axis=1
        )
        monthly["_coverage_before_timing"] = monthly.apply(
            lambda r: (r["_pv"] / r["_demand"] * 100) if r["_demand"] > 0 else None,
            axis=1
        )
        if monthly["_direct_ss"].notna().any():
            best_month = int(monthly["_direct_ss"].idxmax())
            worst_month = int(monthly["_direct_ss"].idxmin())
            best_screen_month = int(monthly["_coverage_before_timing"].idxmax())
            monthly_lines.append(
                f"Best month for direct self-sufficiency: {MONTHS[best_month - 1]} ({_format_number(monthly.loc[best_month, '_direct_ss'], '%', 1)}). "
                f"Worst month: {MONTHS[worst_month - 1]} ({_format_number(monthly.loc[worst_month, '_direct_ss'], '%', 1)})."
            )
            monthly_lines.append(
                f"Best monthly PV/demand screen before timing losses: {MONTHS[best_screen_month - 1]} "
                f"({_format_number(monthly.loc[best_screen_month, '_coverage_before_timing'], '%', 1)}). "
                "This is useful for seasonal sizing, but it is not direct hourly self-sufficiency."
            )

        pv_work["_hour"] = pv_work["_dt"].dt.hour
        hourly = pv_work.groupby("_hour")[["_pv", "_demand"]].mean()
        if not hourly.empty:
            mismatch = hourly["_demand"] - hourly["_pv"]
            worst_hour = int(mismatch.idxmax())
            surplus_hours = [int(h) for h, row in hourly.iterrows() if row["_pv"] > row["_demand"]]
            if surplus_hours:
                if len(surplus_hours) > 1 and surplus_hours == list(range(min(surplus_hours), max(surplus_hours) + 1)):
                    surplus_text = f"roughly from {min(surplus_hours)}:00 to {max(surplus_hours)}:00"
                else:
                    surplus_text = ", ".join(f"{h}:00" for h in surplus_hours)
                monthly_lines.append(f"Typical daily mismatch: strongest deficit occurs around {worst_hour}:00; surplus hours occur at {surplus_text}.")
            else:
                monthly_lines.append(f"Typical daily mismatch: strongest deficit occurs around {worst_hour}:00; PV rarely exceeds demand in the average hourly profile.")

    lines = [
        f"Sources: {pv_source}; {demand_source}.",
        f"Scale: {scale}.",
    ]
    if selected_buildings:
        lines.append(f"Selected buildings: {', '.join(selected_buildings)}.")
        lines.append(f"Important scale rule: do not use district PV total {_format_number(district_annual_pv, ' kWh/year')} or Total_demand.csv as the selected building/cluster result.")
    lines.append(f"Annual PV generation for this scope: {_format_number(annual_pv, ' kWh/year')} ({_format_number(annual_pv / 1000, ' MWh/year', 1)}).")
    lines.append(f"Annual electricity demand for this scope: {_format_number(annual_demand, ' kWh/year')} ({_format_number(annual_demand / 1000, ' MWh/year', 1)}).")
    lines.append(f"Direct self-sufficiency: {_format_number(direct_self_sufficiency, '%', 1)} of annual demand is covered at the same hour by PV generation.")
    lines.append(f"Annual PV coverage screen: PV generation equals {_format_number(annual_coverage, '%', 1)} of annual demand before timing losses.")
    lines.append(f"Self-consumption: {_format_number(self_consumption, '%', 1)} of PV generation is used directly on site.")
    lines.append(f"Annual exported surplus: {_format_number(surplus, ' kWh/year')} ({_format_number(surplus / 1000, ' MWh/year', 1)}).")
    lines.append(f"Annual grid import/deficit after hourly PV offset: {_format_number(deficit, ' kWh/year')} ({_format_number(deficit / 1000, ' MWh/year', 1)}).")
    lines.extend(monthly_lines)
    lines.append("Interpretation boundary: Self-Sufficiency owns demand matching. Do not use solar irradiation values as PV generation, and do not use district totals when selected buildings are supplied.")
    return "\n".join(lines)


def compute_storage_necessity_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total.csv")
                     and "buildings" not in k), None)
    if not pv_fname:
        return "No PV total hourly file is available, so storage necessity cannot be calculated reliably."

    pv_df = files.get(pv_fname)
    gen_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None
    if pv_df is None or gen_col is None:
        return f"{pv_fname} is available, but no PV generation column was found."

    district_annual_pv = float(pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).sum())
    pv_scale = 1.0
    pv_source = f"{pv_fname} district hourly total"
    bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
    pv_b = files.get(bldg_fname)
    if selected_buildings and pv_b is not None:
        name_col = _find_metric_col(pv_b, "name", "building")
        gen_b_col = _find_metric_col(pv_b, "E_PV_gen", "E_PV", "gen")
        if name_col and gen_b_col:
            selected_pv = pv_b[pv_b[name_col].isin(selected_buildings)]
            selected_annual_pv = float(pd.to_numeric(selected_pv[gen_b_col], errors="coerce").fillna(0).sum())
            if selected_annual_pv > 0 and district_annual_pv > 0:
                pv_scale = selected_annual_pv / district_annual_pv
                pv_source = f"{bldg_fname} filtered to selected building(s), with hourly profile scaled from {pv_fname}"

    demand_hourly, demand_source = _sum_hourly_demand_series(files, selected_buildings)
    if demand_hourly is None or len(demand_hourly) == 0:
        return "No hourly electricity demand file was found for the selected scope, so storage necessity cannot be calculated reliably."

    pv_hourly = pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).reset_index(drop=True) * pv_scale
    n = min(len(pv_hourly), len(demand_hourly))
    pv_hourly = pv_hourly.iloc[:n].reset_index(drop=True)
    demand_hourly = demand_hourly.iloc[:n].reset_index(drop=True)

    annual_pv = float(pv_hourly.sum())
    annual_demand = float(demand_hourly.sum())
    self_consumed = float(pd.concat([pv_hourly, demand_hourly], axis=1).min(axis=1).sum())
    surplus_hourly = (pv_hourly - demand_hourly).clip(lower=0)
    deficit_hourly = (demand_hourly - pv_hourly).clip(lower=0)
    annual_surplus = float(surplus_hourly.sum())
    annual_deficit = float(deficit_hourly.sum())
    direct_ss = self_consumed / annual_demand * 100 if annual_demand > 0 else None
    self_consumption = self_consumed / annual_pv * 100 if annual_pv > 0 else None
    annual_screen = annual_pv / annual_demand * 100 if annual_demand > 0 else None
    peak_pv = float(pv_hourly.max())
    peak_demand = float(demand_hourly.max())

    date_col = _find_metric_col(pv_df, "date", "time")
    monthly_line = ""
    room_line = ""
    if date_col:
        work = pv_df.iloc[:n].copy()
        work["_dt"] = pd.to_datetime(work[date_col], utc=True, errors="coerce")
        work["_month"] = work["_dt"].dt.month
        work["_date"] = work["_dt"].dt.date
        work["_pv"] = pv_hourly.values
        work["_demand"] = demand_hourly.values
        work["_self"] = pd.concat([work["_pv"], work["_demand"]], axis=1).min(axis=1)
        work["_surplus"] = surplus_hourly.values
        monthly = work.groupby("_month")[["_pv", "_demand", "_self"]].sum().reindex(range(1, 13), fill_value=0)
        monthly["_direct_ss"] = monthly.apply(lambda r: r["_self"] / r["_demand"] * 100 if r["_demand"] > 0 else None, axis=1)
        monthly["_pv_demand"] = monthly.apply(lambda r: r["_pv"] / r["_demand"] * 100 if r["_demand"] > 0 else None, axis=1)
        if monthly["_direct_ss"].notna().any():
            winter_month = int(monthly["_direct_ss"].idxmin())
            summer_month = int(monthly["_direct_ss"].idxmax())
            monthly_line = (
                f"Seasonal signal: direct self-sufficiency ranges from {MONTHS[winter_month - 1]} "
                f"({_format_number(monthly.loc[winter_month, '_direct_ss'], '%', 1)}) to {MONTHS[summer_month - 1]} "
                f"({_format_number(monthly.loc[summer_month, '_direct_ss'], '%', 1)})."
            )

        daily_surplus = work.groupby("_date")["_surplus"].sum()
        if not daily_surplus.empty:
            usable_kwh = float(daily_surplus.quantile(0.90))
            if usable_kwh > 0:
                low_area = usable_kwh * 0.08
                high_area = usable_kwh * 0.12
                room_line = (
                    f"Battery-ready space screen: a 90th-percentile daily surplus is about {_format_number(usable_kwh, ' kWh', 0)}. "
                    f"Reserve roughly {low_area:.0f}-{high_area:.0f} m2 near the inverter/main electrical room if short-term storage is kept in the concept."
                )

    if annual_surplus > annual_pv * 0.15:
        short_term = "Yes - short-term storage or load shifting is worth planning because a meaningful part of PV generation is exported."
    elif annual_surplus > annual_pv * 0.03:
        short_term = "Maybe - keep the electrical room and risers storage-ready, but do not let batteries drive the concept yet."
    else:
        short_term = "No strong short-term battery signal - most PV is already used directly by the building."

    if annual_screen < 70 or annual_deficit > annual_demand * 0.35:
        seasonal = "Seasonal/grid dependency remains. Treat this as grid interaction or district-scale seasonal storage, not a large building battery room."
    else:
        seasonal = "Seasonal dependency is moderate. Building-scale daily storage is more relevant than seasonal storage."

    lines = [
        f"Sources: {pv_source}; {demand_source}.",
        f"Scale: {scale}.",
    ]
    if selected_buildings:
        lines.append(f"Selected buildings: {', '.join(selected_buildings)}.")
        lines.append(f"Important scale rule: this storage screen uses selected building/cluster demand files and scaled PV, not district totals.")
    lines.append(f"Annual PV generation: {_format_number(annual_pv, ' kWh/year')}; annual electricity demand: {_format_number(annual_demand, ' kWh/year')}.")
    lines.append(f"Annual PV/demand screen before timing losses: {_format_number(annual_screen, '%', 1)}; direct hourly self-sufficiency: {_format_number(direct_ss, '%', 1)}.")
    lines.append(f"Self-consumption: {_format_number(self_consumption, '%', 1)}; exported surplus: {_format_number(annual_surplus, ' kWh/year')}; grid import after PV: {_format_number(annual_deficit, ' kWh/year')}.")
    lines.append(f"Peak PV: {_format_number(peak_pv, ' kW', 1)}; peak demand: {_format_number(peak_demand, ' kW', 1)}.")
    lines.append(f"Short-term storage signal: {short_term}")
    if monthly_line:
        lines.append(monthly_line)
    lines.append(f"Long-term storage signal: {seasonal}")
    if room_line:
        lines.append(room_line)
    lines.append("Interpretation boundary: Storage Necessity owns short-term load shifting and seasonal grid-dependency. Do not present district solar summaries as selected-building storage results.")
    return "\n".join(lines)


def _grid_carbon_factor_for_metrics(cea_data):
    grid_df = cea_data.get("files", {}).get("GRID.csv")
    carbon_col = _find_metric_col(grid_df, "GHG_kgCO2MJ", "CO2", "co2", "emission", "GHG") if grid_df is not None else None
    if carbon_col:
        try:
            value = float(pd.to_numeric(grid_df[carbon_col], errors="coerce").dropna().iloc[0])
            return value * 3.6 if "MJ" in carbon_col else value, f"GRID.csv column {carbon_col}"
        except Exception:
            pass
    return 0.4, "fallback estimate 0.4 kgCO2/kWh"


def compute_carbon_footprint_metrics(cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total.csv")
                     and "buildings" not in k), None)
    if not pv_fname:
        return "No PV total hourly file is available, so BIPV avoided carbon cannot be calculated reliably."

    pv_df = files.get(pv_fname)
    gen_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None
    if pv_df is None or gen_col is None:
        return f"{pv_fname} is available, but no PV generation column was found."

    district_annual_pv = float(pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).sum())
    annual_pv = district_annual_pv
    pv_scale = 1.0
    pv_source = f"{pv_fname} district hourly total"

    pv_b = files.get(pv_fname.replace("_total.csv", "_total_buildings.csv"))
    if selected_buildings and pv_b is not None:
        name_col = _find_metric_col(pv_b, "name", "building")
        gen_b_col = _find_metric_col(pv_b, "E_PV_gen", "E_PV", "gen")
        if name_col and gen_b_col:
            selected_pv = pv_b[pv_b[name_col].isin(selected_buildings)]
            selected_annual = float(pd.to_numeric(selected_pv[gen_b_col], errors="coerce").fillna(0).sum())
            if selected_annual > 0:
                annual_pv = selected_annual
                pv_scale = annual_pv / district_annual_pv if district_annual_pv > 0 else 1.0
                pv_source = f"{pv_fname.replace('_total.csv', '_total_buildings.csv')} filtered to selected building(s), with hourly profile scaled from {pv_fname}"

    demand_hourly, demand_source = _sum_hourly_demand_series(files, selected_buildings)
    if demand_hourly is None or len(demand_hourly) == 0:
        return "No hourly electricity demand file was found for the selected scope, so carbon footprint cannot be calculated reliably."

    pv_hourly = pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).reset_index(drop=True) * pv_scale
    n = min(len(pv_hourly), len(demand_hourly))
    pv_hourly = pv_hourly.iloc[:n].reset_index(drop=True)
    demand_hourly = demand_hourly.iloc[:n].reset_index(drop=True)
    annual_pv = float(pv_hourly.sum())
    annual_demand = float(demand_hourly.sum())
    self_consumed = float(pd.concat([pv_hourly, demand_hourly], axis=1).min(axis=1).sum())

    grid_carbon, grid_source = _grid_carbon_factor_for_metrics(cea_data)
    baseline_tco2 = annual_demand * grid_carbon / 1000
    avoided_tco2 = self_consumed * grid_carbon / 1000
    net_tco2 = max(baseline_tco2 - avoided_tco2, 0)
    abatement = avoided_tco2 / baseline_tco2 * 100 if baseline_tco2 > 0 else None

    lines = [
        f"Sources: {pv_source}; {demand_source}; grid carbon from {grid_source}.",
        f"Scale: {scale}.",
    ]
    if selected_buildings:
        lines.append(f"Selected buildings: {', '.join(selected_buildings)}.")
        lines.append(f"Important scale rule: do not use district PV total {_format_number(district_annual_pv, ' kWh/year')} for this selected building/cluster result.")
    lines.append(f"Annual electricity demand: {_format_number(annual_demand, ' kWh/year')}.")
    lines.append(f"Annual PV generation: {_format_number(annual_pv, ' kWh/year')}.")
    lines.append(f"Hourly PV used on site for carbon offset: {_format_number(self_consumed, ' kWh/year')}.")
    lines.append(f"Grid carbon factor used: {_format_number(grid_carbon, ' kgCO2/kWh', 3)}.")
    lines.append(f"Baseline electricity carbon footprint: {_format_number(baseline_tco2, ' tCO2/year', 1)}.")
    lines.append(f"BIPV avoided carbon: {_format_number(avoided_tco2, ' tCO2/year', 1)}.")
    lines.append(f"Net electricity carbon after BIPV: {_format_number(net_tco2, ' tCO2/year', 1)}.")
    lines.append(f"Annual electricity-carbon reduction: {_format_number(abatement, '%', 1)}.")
    lines.append("Interpretation boundary: this is an annual electricity-carbon footprint screen. Do not discuss panel manufacturing carbon or carbon payback years here.")
    return "\n".join(lines)


def _pv_scope_for_metrics(cea_data, selected_buildings=None):
    files = cea_data.get("files", {})
    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total.csv")
                     and "buildings" not in k), None)
    if not pv_fname:
        return None
    pv_df = files.get(pv_fname)
    gen_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None
    if pv_df is None or not gen_col:
        return None

    district_annual = float(pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).sum())
    annual = district_annual
    roof_area = facade_area = 0.0
    source = f"{pv_fname} district total"
    pv_b = files.get(pv_fname.replace("_total.csv", "_total_buildings.csv"))
    if pv_b is not None:
        name_col = _find_metric_col(pv_b, "name", "building")
        gen_b_col = _find_metric_col(pv_b, "E_PV_gen", "E_PV", "gen")
        df_use = pv_b.copy()
        if selected_buildings and name_col:
            df_use = df_use[df_use[name_col].isin(selected_buildings)]
            source = f"{pv_fname.replace('_total.csv', '_total_buildings.csv')} filtered to selected building(s)"
        if gen_b_col and not df_use.empty:
            annual = float(pd.to_numeric(df_use[gen_b_col], errors="coerce").fillna(0).sum())
        roof_col = _find_metric_col(df_use, "PV_roofs_top_m2")
        if roof_col:
            roof_area = float(pd.to_numeric(df_use[roof_col], errors="coerce").fillna(0).sum())
        for direction in ["south", "east", "west", "north"]:
            col = _find_metric_col(df_use, f"PV_walls_{direction}_m2")
            if col:
                facade_area += float(pd.to_numeric(df_use[col], errors="coerce").fillna(0).sum())
    return {
        "source": source,
        "annual_kwh": annual,
        "district_annual_kwh": district_annual,
        "roof_area_m2": roof_area,
        "facade_area_m2": facade_area,
        "area_m2": roof_area + facade_area,
    }


def compute_carbon_payback_metrics(cea_data, selected_buildings=None, scale="District"):
    scope = _pv_scope_for_metrics(cea_data, selected_buildings)
    if not scope:
        return "No PV result file is available, so carbon payback cannot be calculated reliably."
    panel_df = cea_data.get("files", {}).get("PHOTOVOLTAIC_PANELS.csv")
    embodied = 329.0
    if panel_df is not None and not panel_df.empty:
        emb_col = _find_metric_col(panel_df, "module_embodied", "embodied", "CO2")
        if emb_col:
            try:
                embodied = float(pd.to_numeric(panel_df[emb_col], errors="coerce").dropna().iloc[0])
            except Exception:
                pass
    grid_carbon, grid_source = _grid_carbon_factor_for_metrics(cea_data)
    area = scope["area_m2"] if scope["area_m2"] > 0 else None
    embodied_total = embodied * area if area else None
    annual_avoided = scope["annual_kwh"] * grid_carbon
    payback = embodied_total / annual_avoided if embodied_total and annual_avoided > 0 else None
    lines = [
        f"Sources: {scope['source']}; PHOTOVOLTAIC_PANELS.csv; grid carbon from {grid_source}.",
        f"Scale: {scale}.",
    ]
    if selected_buildings:
        lines.append(f"Selected buildings: {', '.join(selected_buildings)}.")
        lines.append(f"Important scale rule: do not use district PV total {_format_number(scope['district_annual_kwh'], ' kWh/year')} for this selected building/cluster result.")
    lines.append(f"Annual PV generation: {_format_number(scope['annual_kwh'], ' kWh/year')}.")
    lines.append(f"CEA simulated active PV module area used for embodied carbon: {_format_number(area, ' m2', 1)}.")
    lines.append(f"Panel embodied carbon used: {_format_number(embodied, ' kgCO2/m2', 1)}.")
    lines.append(f"Total embodied panel carbon: {_format_number(embodied_total / 1000 if embodied_total else None, ' tCO2', 1)}.")
    lines.append(f"Annual avoided carbon: {_format_number(annual_avoided / 1000, ' tCO2/year', 1)}.")
    lines.append(f"Carbon payback period: {_format_number(payback, ' years', 1)}.")
    return "\n".join(lines)


def compute_economic_viability_metrics(cea_data, selected_buildings=None, scale="District"):
    screen = compute_basic_economic_project_screen(cea_data, selected_buildings)
    if not screen:
        return "No PV/economic screen could be calculated from the extracted files."
    prefix = [
        f"Scale: {scale}.",
        "Use this project-specific screen for Cost Analysis and Investment Payback. Do not use district totals for selected building/cluster results.",
    ]
    if selected_buildings:
        prefix.append(f"Selected buildings: {', '.join(selected_buildings)}.")
    return "\n".join(prefix + [screen])


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
            f"roof cost {_format_number(row['roof_cost'], ' €/m2', 1)}; facade cost {_format_number(row['facade_cost'], ' €/m2', 1)}."
        )
    return "\n".join(lines)


def _sum_hourly_demand_series(files, selected_buildings=None):
    demand_frames = []
    if selected_buildings:
        for bname in selected_buildings:
            df = files.get(f"{bname}.csv")
            if df is not None:
                demand_frames.append(df)
    else:
        demand_frames = [
            df for fname, df in files.items()
            if fname.startswith("B") and fname.endswith(".csv") and len(fname) <= 10
        ]

    series = None
    source = None
    for df in demand_frames:
        col = _find_metric_col(df, "E_sys_kWh", "GRID", "E_tot")
        if not col:
            continue
        values = pd.to_numeric(df[col], errors="coerce").fillna(0).reset_index(drop=True)
        series = values if series is None else series.add(values, fill_value=0)
        source = "selected building hourly demand files" if selected_buildings else "all building hourly demand files"

    if series is not None:
        return series, source

    total_df = files.get("Total_demand_hourly.csv")
    if total_df is None:
        total_df = files.get("Total_demand.csv")
    total_col = _find_metric_col(total_df, "E_sys_kWh", "GRID", "E_tot", "total") if total_df is not None else None
    if total_df is not None and total_col:
        return pd.to_numeric(total_df[total_col], errors="coerce").fillna(0).reset_index(drop=True), "total demand file"

    return None, None


def compute_basic_economic_project_screen(cea_data, selected_buildings=None):
    files = cea_data.get("files", {})
    weather_header = files.get("weather_header", "")
    template_name, template = _select_economic_template(weather_header)
    if not template:
        return ""

    currency = template.get("currency", "EUR")
    sym = template.get("currency_symbol", "€")

    pv_fname = next((k for k in files
                     if k.startswith("PV_PV") and k.endswith("_total.csv")
                     and "buildings" not in k), None)
    if not pv_fname:
        return "Project-specific early BIPV economic screen: no PV hourly total file was found, so project generation/value cannot be calculated."

    pv_df = files.get(pv_fname)
    pv_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None
    if pv_df is None or not pv_col:
        return "Project-specific early BIPV economic screen: PV generation column was not found in the PV result file."

    pv_buildings_df = files.get(pv_fname.replace("_total.csv", "_total_buildings.csv"))
    selected_pv_df = pv_buildings_df
    name_col = _find_metric_col(pv_buildings_df, "name", "building") if pv_buildings_df is not None else None
    if selected_buildings and pv_buildings_df is not None and name_col:
        selected_pv_df = pv_buildings_df[pv_buildings_df[name_col].isin(selected_buildings)].copy()

    pv_b_col = _find_metric_col(selected_pv_df, "E_PV_gen", "E_PV", "gen") if selected_pv_df is not None else None
    if selected_pv_df is not None and pv_b_col and not selected_pv_df.empty:
        annual_pv_kwh = float(pd.to_numeric(selected_pv_df[pv_b_col], errors="coerce").fillna(0).sum())
    else:
        annual_pv_kwh = float(pd.to_numeric(pv_df[pv_col], errors="coerce").fillna(0).sum())

    district_pv_kwh = float(pd.to_numeric(pv_df[pv_col], errors="coerce").fillna(0).sum())
    pv_scale = annual_pv_kwh / district_pv_kwh if district_pv_kwh > 0 else 1.0
    pv_hourly = pd.to_numeric(pv_df[pv_col], errors="coerce").fillna(0).reset_index(drop=True) * pv_scale

    demand_hourly, demand_source = _sum_hourly_demand_series(files, selected_buildings)
    annual_demand_kwh = float(demand_hourly.sum()) if demand_hourly is not None else None
    if demand_hourly is not None and len(demand_hourly) and len(pv_hourly):
        n = min(len(demand_hourly), len(pv_hourly))
        self_consumed_kwh = float(pd.concat([pv_hourly.iloc[:n], demand_hourly.iloc[:n]], axis=1).min(axis=1).sum())
        exported_kwh = max(annual_pv_kwh - self_consumed_kwh, 0.0)
        if annual_pv_kwh > 0 and exported_kwh < annual_pv_kwh * 0.01:
            exported_kwh = 0.0
        self_consumption_note = f"hourly overlap of scaled PV generation and {demand_source}"
    else:
        self_consumed_kwh = None
        exported_kwh = None
        self_consumption_note = "hourly demand was not available"

    roof_area = facade_area = 0.0
    if selected_pv_df is not None and not selected_pv_df.empty:
        roof_col = _find_metric_col(selected_pv_df, "PV_roofs_top_m2")
        if roof_col:
            roof_area = float(pd.to_numeric(selected_pv_df[roof_col], errors="coerce").fillna(0).sum())
        for direction in ["south", "east", "west", "north"]:
            col = _find_metric_col(selected_pv_df, f"PV_walls_{direction}_m2")
            if col:
                facade_area += float(pd.to_numeric(selected_pv_df[col], errors="coerce").fillna(0).sum())

    roof_cost_lo = template.get("bipv_cost_roof_m2_low")
    roof_cost_hi = template.get("bipv_cost_roof_m2_high")
    facade_cost_lo = template.get("bipv_cost_facade_m2_low")
    facade_cost_hi = template.get("bipv_cost_facade_m2_high")
    investment_lo = investment_hi = None
    if (roof_area + facade_area) > 0 and all(v is not None for v in [roof_cost_lo, roof_cost_hi, facade_cost_lo, facade_cost_hi]):
        investment_lo = roof_area * float(roof_cost_lo) + facade_area * float(facade_cost_lo)
        investment_hi = roof_area * float(roof_cost_hi) + facade_area * float(facade_cost_hi)

    use_fractions, dominant_use = detect_building_use_types(cea_data, selected_buildings)
    use_prices = template.get("electricity_by_use_type", {})
    tariff = None
    tariff_note = ""
    if use_fractions and use_prices:
        weighted = 0.0
        weight_sum = 0.0
        for use, fraction in use_fractions.items():
            price = use_prices.get(use, {}).get("price")
            if price is not None:
                weighted += float(price) * float(fraction)
                weight_sum += float(fraction)
        if weight_sum > 0:
            tariff = weighted / weight_sum
            tariff_note = "weighted by detected building use type mix"
    if tariff is None and dominant_use and use_prices.get(dominant_use, {}).get("price") is not None:
        tariff = float(use_prices[dominant_use]["price"])
        tariff_note = f"dominant detected use type: {dominant_use}"
    if tariff is None and template.get("electricity_price_kwh") is not None:
        tariff = float(template["electricity_price_kwh"])
        tariff_note = "regional baseline tariff"

    export_comp = template.get("export_compensation_kwh")
    annual_value = None
    if self_consumed_kwh is not None and tariff is not None:
        annual_value = self_consumed_kwh * tariff
        if exported_kwh is not None and exported_kwh > 0 and export_comp is not None:
            annual_value += exported_kwh * float(export_comp)

    payback_lo = payback_hi = None
    if investment_lo is not None and investment_hi is not None and annual_value and annual_value > 0:
        payback_lo = investment_lo / annual_value
        payback_hi = investment_hi / annual_value

    lines = [
        f"Project-specific early BIPV economic screen ({currency}, from {template_name.replace('_', ' ').title()} baseline):",
        f"- CEA simulated active PV module area: roof {_format_number(roof_area, ' m2', 1)}; facade {_format_number(facade_area, ' m2', 1)}.",
        f"- Annual PV generation from CEA: {_format_number(annual_pv_kwh, ' kWh/year')}.",
    ]
    if annual_demand_kwh is not None:
        lines.append(f"- Annual electricity demand used for value screen: {_format_number(annual_demand_kwh, ' kWh/year')}.")
    if self_consumed_kwh is not None:
        sc_pct = self_consumed_kwh / annual_pv_kwh * 100 if annual_pv_kwh > 0 else None
        lines.append(
            f"- Hourly self-consumption estimate: {_format_number(self_consumed_kwh, ' kWh/year')} "
            f"({_format_number(sc_pct, '% of PV generation', 1)}) from {self_consumption_note}."
        )
        if exported_kwh and exported_kwh > 0:
            lines.append(f"- Exported surplus estimate: {_format_number(exported_kwh, ' kWh/year')}.")
        else:
            lines.append("- Exported surplus estimate: none detected from hourly PV-demand overlap.")
    if investment_lo is not None and investment_hi is not None:
        lines.append(
            f"- Installed BIPV investment screen: {sym} {_format_number(investment_lo, '', 0)}–{sym} {_format_number(investment_hi, '', 0)} "
            f"(roof {sym} {roof_cost_lo}–{sym} {roof_cost_hi}/m2; facade {sym} {facade_cost_lo}–{sym} {facade_cost_hi}/m2)."
        )
    if tariff is not None:
        if exported_kwh and exported_kwh > 0 and export_comp is not None:
            export_text = f"; export compensation {sym} {float(export_comp):.2f}/kWh applied only to detected exported PV"
        else:
            export_text = "; no export value added because no exported surplus was detected"
        lines.append(f"- Value assumptions: electricity tariff {sym} {tariff:.2f}/kWh ({tariff_note}){export_text}.")
    if annual_value is not None:
        lines.append(f"- Estimated annual electricity value: {sym} {_format_number(annual_value, '', 0)}/year.")
    if payback_lo is not None and payback_hi is not None:
        lines.append(f"- Simple payback screen from project data: {_format_number(payback_lo, ' years', 1)}–{_format_number(payback_hi, ' years', 1)}.")
    lines.append(f"Currency rule: all user-facing money values must stay in {currency} ({sym}); convert any web result in another currency before presenting it.")

    return "\n".join(lines)


def compute_pv_coverage_scenario_values(cea_data, selected_buildings=None, coverage_pct=100):
    """Local what-if calculation: roof PV stays fixed, facade PV scales with the slider."""
    scope = _pv_scope_for_metrics(cea_data, selected_buildings)
    if not scope:
        return None

    fraction = max(0, min(float(coverage_pct), 100)) / 100
    files = cea_data.get("files", {})

    roof_gen = 0.0
    facade_gen = 0.0
    roof_area_base = scope["roof_area_m2"]
    facade_area_base = scope["facade_area_m2"]
    pv_fname = next((k for k in files if k.startswith("PV_PV") and k.endswith("_total.csv") and "buildings" not in k), None)
    pv_buildings = files.get(pv_fname.replace("_total.csv", "_total_buildings.csv")) if pv_fname else None
    if pv_buildings is not None and not pv_buildings.empty:
        df_use = pv_buildings.copy()
        name_col = _find_metric_col(df_use, "name", "building")
        if selected_buildings and name_col:
            df_use = df_use[df_use[name_col].isin(selected_buildings)]
        roof_e_col = _find_metric_col(df_use, "PV_roofs_top_E_kWh")
        if roof_e_col:
            roof_gen = float(pd.to_numeric(df_use[roof_e_col], errors="coerce").fillna(0).sum())
        for direction in ["south", "east", "west", "north"]:
            col = _find_metric_col(df_use, f"PV_walls_{direction}_E_kWh")
            if col:
                facade_gen += float(pd.to_numeric(df_use[col], errors="coerce").fillna(0).sum())

    if roof_gen <= 0 and facade_gen <= 0:
        roof_gen = scope["annual_kwh"]

    base_pv = roof_gen + facade_gen
    scenario_pv = roof_gen + facade_gen * fraction
    roof_area = roof_area_base
    facade_area = facade_area_base * fraction
    active_area = roof_area + facade_area

    demand_hourly, demand_source = _sum_hourly_demand_series(files, selected_buildings)
    annual_demand = float(demand_hourly.sum()) if demand_hourly is not None else None

    self_consumed = export = self_sufficiency = annual_coverage = None
    if pv_fname and demand_hourly is not None and len(demand_hourly) > 0:
        pv_df = files.get(pv_fname)
        gen_col = _find_metric_col(pv_df, "E_PV_gen", "E_PV", "gen") if pv_df is not None else None
        if gen_col:
            district_annual = float(pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).sum())
            scale = scenario_pv / district_annual if district_annual > 0 else 0
            pv_hourly = pd.to_numeric(pv_df[gen_col], errors="coerce").fillna(0).reset_index(drop=True) * scale
            n = min(len(pv_hourly), len(demand_hourly))
            pv_hourly = pv_hourly.iloc[:n].reset_index(drop=True)
            demand_use = demand_hourly.iloc[:n].reset_index(drop=True)
            self_consumed = float(pd.concat([pv_hourly, demand_use], axis=1).min(axis=1).sum())
            export = max(float(pv_hourly.sum()) - self_consumed, 0.0)
            annual_demand = float(demand_use.sum())
    elif annual_demand is not None:
        self_consumed = min(scenario_pv, annual_demand)
        export = max(scenario_pv - self_consumed, 0.0)

    if annual_demand and annual_demand > 0:
        annual_coverage = scenario_pv / annual_demand * 100
        if self_consumed is not None:
            self_sufficiency = self_consumed / annual_demand * 100

    panel_df = files.get("PHOTOVOLTAIC_PANELS.csv")
    roof_cost = facade_cost = None
    embodied = None
    if panel_df is not None and not panel_df.empty:
        try:
            roof_col = _find_metric_col(panel_df, "cost_roof", "roof")
            facade_col = _find_metric_col(panel_df, "cost_facade", "facade")
            emb_col = _find_metric_col(panel_df, "module_embodied", "embodied", "CO2")
            roof_cost = float(pd.to_numeric(panel_df[roof_col], errors="coerce").dropna().iloc[0]) if roof_col else None
            facade_cost = float(pd.to_numeric(panel_df[facade_col], errors="coerce").dropna().iloc[0]) if facade_col else None
            embodied = float(pd.to_numeric(panel_df[emb_col], errors="coerce").dropna().iloc[0]) if emb_col else None
        except Exception:
            pass

    investment = None
    if roof_cost is not None and facade_cost is not None:
        investment = roof_area * roof_cost + facade_area * facade_cost

    grid_carbon, grid_source = _grid_carbon_factor_for_metrics(cea_data)
    avoided_tco2 = self_consumed * grid_carbon / 1000 if self_consumed is not None else None
    net_tco2 = max((annual_demand or 0) * grid_carbon / 1000 - (avoided_tco2 or 0), 0) if annual_demand is not None else None
    embodied_tco2 = active_area * embodied / 1000 if embodied is not None else None

    return {
        "coverage_pct": coverage_pct,
        "base_pv_kwh": base_pv,
        "scenario_pv_kwh": scenario_pv,
        "roof_pv_kwh": roof_gen,
        "facade_pv_kwh_at_100pct": facade_gen,
        "active_area_m2": active_area,
        "roof_area_m2": roof_area,
        "facade_area_m2": facade_area,
        "facade_area_100pct_m2": facade_area_base,
        "annual_demand_kwh": annual_demand,
        "self_consumed_kwh": self_consumed,
        "export_kwh": export,
        "self_sufficiency_pct": self_sufficiency,
        "annual_coverage_pct": annual_coverage,
        "investment": investment,
        "avoided_tco2": avoided_tco2,
        "net_tco2": net_tco2,
        "embodied_tco2": embodied_tco2,
        "grid_source": grid_source,
        "demand_source": demand_source,
    }


def format_pv_coverage_scenario_for_recipe(values):
    if not values:
        return "No PV coverage scenario has been saved."
    return (
        f"Saved PV Coverage Scenario: roof PV kept at 100%; facade PV set to {values['coverage_pct']:.0f}% of the CEA simulated facade PV area; "
        f"active PV area {_format_number(values['active_area_m2'], ' m2', 1)} "
        f"(roof {_format_number(values['roof_area_m2'], ' m2', 1)}; facade {_format_number(values['facade_area_m2'], ' m2', 1)}); "
        f"annual PV generation {_format_number(values['scenario_pv_kwh'], ' kWh/year')}; "
        f"self-sufficiency {_format_number(values['self_sufficiency_pct'], '%', 1)}; "
        f"annual PV coverage before timing losses {_format_number(values['annual_coverage_pct'], '%', 1)}; "
        f"export {_format_number(values['export_kwh'], ' kWh/year')}; "
        f"estimated investment {_format_number(values['investment'], ' €', 0)}; "
        f"avoided carbon {_format_number(values['avoided_tco2'], ' tCO2/year', 1)}; "
        f"net electricity carbon {_format_number(values['net_tco2'], ' tCO2/year', 1)}."
    )


def render_pv_coverage_scenario_tool(cea_data, selected_buildings=None):
    if st.session_state.get("pv_coverage_scenario"):
        st.info("A PV coverage scenario is saved for the Design Integration Recipe. You can adjust the slider and save again to replace it.")
    current = st.session_state.get("pv_coverage_pct", 50)
    if "pv_coverage_pct_widget" not in st.session_state:
        st.session_state.pv_coverage_pct_widget = int(current)

    def _commit_pv_coverage_pct():
        st.session_state.pv_coverage_pct = int(st.session_state.pv_coverage_pct_widget)

    coverage = st.select_slider(
        "How much of the recommended facade PV area are you willing to cover?",
        options=list(range(0, 101, 5)),
        key="pv_coverage_pct_widget",
        on_change=_commit_pv_coverage_pct
    )
    coverage = int(st.session_state.get("pv_coverage_pct", coverage))
    st.caption(f"Estimates below use {int(coverage)}% facade PV coverage.")
    values = compute_pv_coverage_scenario_values(cea_data, selected_buildings, coverage)
    if not values:
        st.warning("No PV result is available for this scenario.")
        return
    st.session_state.pv_coverage_scenario_preview = values

    total_opaque_cells = 19
    active_cells = round(coverage / 100 * total_opaque_cells)
    cells = []
    opaque_seen = 0
    for i in range(24):
        row = i // 6
        col = i % 6
        is_window = (row in (1, 2) and col in (1, 4)) or (row == 2 and col == 2)
        if not is_window:
            opaque_seen += 1
        pv = not is_window and opaque_seen <= active_cells
        cls = "pv-cell" if pv else ("window-cell" if is_window else "wall-cell")
        cells.append(f'<div class="{cls}"></div>')

    html_block = f"""
    <style>
      .scenario-wrap, .scenario-wrap * {{ font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; box-sizing:border-box; }}
      .scenario-wrap {{ display:grid; grid-template-columns: 1fr 1fr; gap:22px; align-items:center; margin-top:12px; background:white; }}
      .scenario-building {{ background:white; border:1px solid #e0dcd4; border-radius:8px; padding:22px; min-height:310px; display:flex; align-items:center; justify-content:center; }}
      .building-face {{ width:270px; height:235px; background:#b8bbc0; border:2px solid #8d9095; display:grid; grid-template-columns:repeat(6, 1fr); grid-template-rows:repeat(4, 1fr); gap:8px; padding:14px; }}
      .wall-cell {{ background:#aeb2b7; border:1px solid rgba(0,0,0,.08); }}
      .window-cell {{ background:#dfe8ee; border:1px solid #f5f8fa; }}
      .pv-cell {{ background:#c8a96e; border:1px solid #9b7b3e; }}
      .scenario-metrics {{ display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:10px; }}
      .metric-box {{ border:1px solid #e0dcd4; border-radius:8px; padding:12px; background:white; }}
      .metric-label {{ color:#777d8c; font-size:12px; margin-bottom:4px; }}
      .metric-value {{ font-weight:600; color:#2d3142; font-size:17px; }}
    </style>
    <div class="scenario-wrap">
      <div class="scenario-building"><div class="building-face">{''.join(cells)}</div></div>
      <div class="scenario-metrics">
        <div class="metric-box"><div class="metric-label">Facade coverage</div><div class="metric-value">{coverage:.0f}%</div></div>
        <div class="metric-box"><div class="metric-label">Facade PV area</div><div class="metric-value">{_format_number(values['facade_area_m2'], ' m2', 1)}</div></div>
        <div class="metric-box"><div class="metric-label">Active PV area</div><div class="metric-value">{_format_number(values['active_area_m2'], ' m2', 1)}</div></div>
        <div class="metric-box"><div class="metric-label">PV generation</div><div class="metric-value">{_format_number(values['scenario_pv_kwh'], ' kWh/yr')}</div></div>
        <div class="metric-box"><div class="metric-label">Self-sufficiency</div><div class="metric-value">{_format_number(values['self_sufficiency_pct'], '%', 1)}</div></div>
        <div class="metric-box"><div class="metric-label">Export</div><div class="metric-value">{_format_number(values['export_kwh'], ' kWh/yr')}</div></div>
        <div class="metric-box"><div class="metric-label">Estimated investment</div><div class="metric-value">{_format_number(values['investment'], ' €', 0)}</div></div>
        <div class="metric-box"><div class="metric-label">Avoided carbon</div><div class="metric-value">{_format_number(values['avoided_tco2'], ' tCO2/yr', 1)}</div></div>
      </div>
    </div>
    """
    st.markdown(html_block, unsafe_allow_html=True)
    st.caption("The roof PV remains at 100% of the CEA simulated roof PV area. The slider only scales the CEA simulated facade PV area; it does not assume the whole physical facade is coverable.")

    if st.button("Save this scenario for Design Integration Recipe", type="primary"):
        st.session_state.pv_coverage_scenario = values
        st.session_state.analysis_log = [
            item for item in st.session_state.get("analysis_log", [])
            if item.get("skill_id") != "optimize-my-design--pv-coverage-scenario"
        ]
        st.session_state.analysis_log.append({
            "skill_id": "optimize-my-design--pv-coverage-scenario",
            "skill_name": "PV Coverage Scenario",
            "mode": "Coverage scenario",
            "scale": st.session_state.tree_scale,
            "selected_buildings": selected_buildings or [],
            "response": format_pv_coverage_scenario_for_recipe(values),
        })
        st.session_state.analysis_ran = False
        st.session_state.chat_history = []
        st.rerun()


def compute_contextual_feasibility_metrics(skill_id, cea_data, selected_buildings=None, scale="District"):
    files = cea_data.get("files", {})
    city, country = _parse_weather_place(files.get("weather_header", ""))
    place = " ".join(p for p in [city, country if country != "-" else ""] if p).strip() or "unknown location"

    lines = [
        f"Project location from weather file: {place}.",
        f"Scale: {scale}.",
    ]
    if selected_buildings:
        lines.append(f"Selected buildings: {', '.join(selected_buildings)}.")

    if skill_id == "site-potential--contextual-feasibility--regulatory-constraints":
        zone_df = files.get("zone_geometry.csv")
        height_lines = []
        if zone_df is not None:
            name_col = _find_metric_col(zone_df, "name", "building")
            height_col = _height_col(zone_df)
            if name_col and height_col:
                check_df = zone_df.copy()
                if selected_buildings:
                    check_df = check_df[check_df[name_col].isin(selected_buildings)]
                heights = []
                for _, row in check_df.iterrows():
                    h = _height_value(row, height_col)
                    if h is not None:
                        heights.append((str(row[name_col]), h))
                if heights:
                    max_name, max_height = max(heights, key=lambda item: item[1])
                    height_lines.append(
                        f"Extracted project building height from zone_geometry.csv: tallest selected/project building is {max_name} at approximately {_format_number(max_height, ' m', 1)}."
                    )
                    if len(heights) <= 6:
                        height_lines.append(
                            "Building heights available: "
                            + "; ".join(f"{name}: {_format_number(height, ' m', 1)}" for name, height in heights)
                            + "."
                        )
                    else:
                        height_lines.append(f"Building heights available for {len(heights)} project buildings.")
        if not height_lines:
            height_lines.append("No usable project building height was extracted from zone_geometry.csv; height-limit comparison can only be qualitative unless a height is supplied elsewhere.")

        lines.extend([
            "This is an internet-first contextual feasibility skill. CEA supplies the project location only; public planning/regulatory sources supply the useful context.",
            "Interpret public facts into early BIPV design decisions: roof vs facade feasibility, visibility/heritage sensitivity, material/reflectivity constraints, mandatory solar requirements, permit path, documentation needs, and approval timeline risk.",
            "Contextual feasibility retrieval logic: use local/city facts when found; if local facts are missing, use national context; if national facts are missing, use regional/continental context; if that is missing, use industry-average guidance only. Always label the level of certainty. Broader context can guide early design but cannot replace parcel-specific approval.",
            "Height/zoning rule: if public/preloaded context supplies a maximum building height, compare it against the extracted project height and flag whether roof-mounted BIPV could approach or exceed the limit. Do not invent a maximum height or roof PV build-up height.",
            "If exact parcel/conservation-zone/height-zone status is missing, do not invent it. Add a short precision note at the end naming the local planning/building authority and asking for facade PV permission route, heritage/conservation status, applicable height limit, whether roof PV equipment counts toward height, material/reflectivity limits, required drawings, and approval timeline.",
            "Mode split: Key insight gives the regulatory stance and priorities; Explain the numbers gives source facts, terms, dates, thresholds, and permit/timeline evidence; Design implication gives the design response and documentation actions."
        ])
        lines.extend(height_lines)
    elif skill_id == "site-potential--contextual-feasibility--basic-economic-signal":
        lines.extend([
            "This is an internet-first contextual feasibility skill. CEA supplies the project location only; public market/energy sources supply the useful context.",
            "Interpret public facts into early BIPV positioning: whether the strongest argument is electricity savings, carbon reduction, regulation/compliance, architectural value, resilience, or client-image value.",
            "Contextual feasibility retrieval logic: use local/city facts when found; if local facts are missing, use national context; if national facts are missing, use regional/continental context; if that is missing, use industry-average benchmarks only. Always label the level of certainty. Broader benchmarks can guide early client framing but cannot replace project tariffs or quotes.",
            "Use the project-specific early BIPV economic screen below when available. It is more useful than generic consultation boilerplate because it combines simulated PV area/generation with local-currency tariff and BIPV cost assumptions.",
            "Benchmarks for orientation only: higher electricity prices strengthen the savings argument; high grid carbon strengthens the carbon argument; simple payback below 8 years is strong, 8-15 is workable, and above 15 years usually needs a carbon, regulatory, or architectural-value argument.",
            "If exact local tariffs, export compensation, BIPV cost range, or payback data are missing, do not invent them. Add a short precision note only after the main answer, naming the utility/energy authority or cost consultant and asking for the exact tariff category, export compensation, subsidy eligibility, and installed BIPV quote assumptions.",
            "Mode split: Key insight gives the client/design argument and priorities; Explain the numbers gives tariffs, carbon, cost, payback, and source evidence; Design implication gives sizing, framing, self-consumption/export strategy, and what not to overpromise."
        ])
        project_screen = compute_basic_economic_project_screen(cea_data, selected_buildings)
        if project_screen:
            lines.append(project_screen)
    return "\n".join(lines)


def compute_compact_metrics(skill_id, cea_data, selected_buildings=None, scale="District"):
    if skill_id == "site-potential--solar-availability--temporal-availability--seasonal-patterns":
        return compute_seasonal_pattern_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--solar-availability--temporal-availability--daily-patterns":
        return compute_daily_pattern_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--solar-availability--temporal-availability--storage-strategy":
        return compute_storage_necessity_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--solar-availability--surface-irradiation":
        return compute_surface_irradiation_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--envelope-suitability":
        return compute_envelope_suitability_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--massing-and-shading-strategy":
        return compute_massing_shading_metrics(cea_data, selected_buildings, scale)
    if skill_id == "site-potential--contextual-feasibility--infrastructure-readiness":
        return compute_infrastructure_readiness_metrics(cea_data, selected_buildings, scale)
    if skill_id == "performance-estimation--energy-generation":
        return compute_energy_generation_metrics(cea_data, selected_buildings, scale)
    if skill_id == "performance-estimation--self-sufficiency":
        return compute_self_sufficiency_metrics(cea_data, selected_buildings, scale)
    if skill_id in (
        "impact-and-viability--carbon-impact--carbon-footprint",
        "impact-and-viability--carbon-impact--operational-carbon-footprint",
    ):
        return compute_carbon_footprint_metrics(cea_data, selected_buildings, scale)
    if skill_id == "impact-and-viability--carbon-impact--carbon-payback":
        return compute_carbon_payback_metrics(cea_data, selected_buildings, scale)
    if skill_id in (
        "impact-and-viability--economic-viability--cost-analysis",
        "impact-and-viability--economic-viability--investment-payback",
    ):
        return compute_economic_viability_metrics(cea_data, selected_buildings, scale)
    if skill_id in (
        "site-potential--contextual-feasibility--regulatory-constraints",
        "site-potential--contextual-feasibility--basic-economic-signal",
    ):
        return compute_contextual_feasibility_metrics(skill_id, cea_data, selected_buildings, scale)
    if skill_id in (
        "performance-estimation--panel-type-tradeoff",
        "optimize-my-design--panel-type-tradeoff",
    ):
        return compute_panel_tradeoff_metrics(cea_data, selected_buildings)
    if skill_id == "optimize-my-design--design-integration-recipe":
        return compute_design_integration_recipe_metrics(cea_data, selected_buildings, scale)
    return None


def _shorten_for_recipe(text, limit=450):
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", str(text)).strip()
    return compact if len(compact) <= limit else compact[:limit].rstrip() + "..."


def get_prior_analysis_context_for_recipe(current_skill_id=None):
    log = st.session_state.get("analysis_log", [])
    if not log:
        return "No prior analysis outputs have been run in this project session yet."

    rows = []
    for item in log[-6:]:
        if item.get("skill_id") == current_skill_id:
            continue
        label = item.get("skill_name") or item.get("skill_id") or "Analysis"
        mode = item.get("mode") or "output"
        scale = item.get("scale") or "scale not set"
        buildings = item.get("selected_buildings") or []
        building_text = f"; buildings: {', '.join(buildings)}" if buildings else ""
        response = _shorten_for_recipe(item.get("response", ""), 360)
        rows.append(f"- {label} ({mode}, {scale}{building_text}): {response}")

    if not rows:
        return "No prior analysis outputs are available apart from the current recipe request."
    return "\n".join(rows)


def compute_design_integration_recipe_metrics(cea_data, selected_buildings=None, scale="District"):
    """Compact, deterministic project facts for the final design recipe."""
    sections = [
        "Recipe evidence packet:",
        f"Scale: {scale}.",
    ]
    if selected_buildings:
        sections.append(f"Selected buildings: {', '.join(selected_buildings)}.")

    metric_builders = [
        ("Surface irradiation", compute_surface_irradiation_metrics),
        ("Envelope suitability", compute_envelope_suitability_metrics),
        ("Massing and shading", compute_massing_shading_metrics),
        ("Infrastructure readiness", compute_infrastructure_readiness_metrics),
        ("Energy generation", compute_energy_generation_metrics),
        ("Self-sufficiency", compute_self_sufficiency_metrics),
        ("Panel type trade-off", lambda data, buildings, _scale: compute_panel_tradeoff_metrics(data, buildings)),
        ("Economic viability", compute_economic_viability_metrics),
    ]
    for label, fn in metric_builders:
        try:
            value = fn(cea_data, selected_buildings, scale)
        except Exception:
            value = None
        if value:
            sections.append(f"\n{label} facts:\n{_shorten_for_recipe(value, 520)}")

    saved_scenario = st.session_state.get("pv_coverage_scenario")
    if saved_scenario:
        sections.append(f"\nSaved PV coverage scenario:\n{format_pv_coverage_scenario_for_recipe(saved_scenario)}")

    prior = get_prior_analysis_context_for_recipe("optimize-my-design--design-integration-recipe")
    sections.append(f"\nPrior interpretations already run in this project session:\n{prior}")
    sections.append(
        "\nRecipe rule: use prior interpretations as design intent/evidence. Use the computed facts above to fill gaps, "
        "but do not claim an interpretation was previously run when it is only a computed fact."
    )
    return "\n".join(sections)


def _clean_search_text(text, limit=700):
    if not text:
        return ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def _decode_duckduckgo_url(url):
    if not url:
        return ""
    url = html.unescape(url)
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc:
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return url


def _official_source_score(url):
    host = urlparse(url).netloc.lower()
    if any(d in host for d in ["admin.ch", ".gov", ".gv.", "swissgrid.ch"]):
        return 5
    if any(d in host for d in ["ewz.ch", "bfe.admin.ch", "elcom.admin.ch"]):
        return 4
    if any(k in host for k in ["energie", "energy", "utility", "grid", "netz", "strom"]):
        return 3
    return 1


def _search_duckduckgo(query, max_results=4):
    try:
        resp = requests.get(
            f"https://duckduckgo.com/html/?q={quote_plus(query)}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        resp.raise_for_status()
    except Exception:
        return []

    html_text = resp.text
    matches = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html_text,
        flags=re.I | re.S,
    )
    results = []
    for raw_url, raw_title in matches:
        url = _decode_duckduckgo_url(raw_url)
        if not url.startswith("http"):
            continue
        title = _clean_search_text(raw_title, 140)
        results.append({"title": title, "url": url})
    results = sorted(results, key=lambda r: _official_source_score(r["url"]), reverse=True)
    return results[:max_results]


def _fetch_public_page_summary(url, keywords=None):
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        resp.raise_for_status()
    except Exception:
        return ""

    text = resp.text[:120000]
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        text,
        flags=re.I | re.S,
    )
    title = _clean_search_text(title_match.group(1), 140) if title_match else ""
    desc = _clean_search_text(desc_match.group(1), 260) if desc_match else ""

    plain = _clean_search_text(text, 5000)
    if keywords is None:
        keywords = [
        "photovoltaic", "pv", "solar", "feed-in", "feed in", "export",
        "grid connection", "connection", "transformer", "capacity",
        "meter", "tariff", "remuneration", "utility", "distribution",
        "netz", "einspeis", "strom", "anschluss",
        ]
    sentences = re.split(r"(?<=[.!?])\s+", plain)
    useful = []
    for sent in sentences:
        s_lower = sent.lower()
        if any(k in s_lower for k in keywords):
            useful.append(sent.strip())
        if len(useful) >= 3:
            break
    parts = [p for p in [title, desc, " ".join(useful)] if p]
    return _clean_search_text(" ".join(parts), 700)


def _fetch_public_grid_page_summary(url):
    return _fetch_public_page_summary(url)


def _parse_weather_place(weather_header):
    location = parse_epw_location(weather_header or "")
    city = (location or {}).get("city") or ""
    country = (location or {}).get("country") or ""
    city_clean = re.sub(r"^(Inducity|City|Weather)[-_ ]", "", city, flags=re.I).strip()
    city_clean = city_clean.split("-")[-1].strip() if "-" in city_clean else city_clean
    return city_clean, country


def _template_match_score(template, city, country):
    match = template.get("match", {})
    haystack = f"{city} {country}".lower()
    score = 0
    for item in match.get("countries", []):
        if item and item.lower() in {country.lower(), haystack}:
            score += 8
        elif item and item.lower() in haystack:
            score += 6
    for item in match.get("keywords", []):
        if item and item.lower() in haystack:
            score += 4
    return score


def _select_economic_template(weather_header):
    templates = load_economic_context()
    if not templates:
        return "generic", {}

    city, country = _parse_weather_place(weather_header)
    best_name = "generic"
    best_score = -1
    for name, template in templates.items():
        if name == "generic":
            continue
        score = _template_match_score(template, city, country)
        if score > best_score:
            best_name = name
            best_score = score

    if best_score <= 0:
        best_name = "generic"
    return best_name, templates.get(best_name, templates.get("generic", {}))


def _format_infrastructure_template(name, template):
    if not template:
        return ""

    def clipped(items, limit):
        return [str(item) for item in (items or [])[:limit]]

    lines = [f"Regional infrastructure baseline: {name.replace('_', ' ').title()}"]
    context = clipped(template.get("context"), 3)
    design = clipped(template.get("design_implications"), 4)
    ask = clipped(template.get("ask_for_precision"), 5)
    sources = clipped(template.get("sources"), 3)
    if context:
        lines.append("Stable context:")
        lines.extend(f"- {item}" for item in context)
    if design:
        lines.append("Concept-design implications:")
        lines.extend(f"- {item}" for item in design)
    if ask:
        lines.append("For a more precise result, ask the responsible utility/grid operator for:")
        lines.extend(f"- {item}" for item in ask)
    if sources:
        lines.append("Baseline sources:")
        lines.extend(f"- {item}" for item in sources)
    return "\n".join(lines)


def _fallback_region_for_country(country):
    c = (country or "").lower()
    if c in {"switzerland", "che", "ch", "germany", "france", "italy", "spain", "netherlands", "austria", "belgium", "denmark", "sweden", "norway", "finland", "united kingdom", "uk", "great britain", "ireland", "portugal", "poland", "czech republic", "greece"}:
        return "Europe"
    if c in {"united states", "usa", "us", "canada", "mexico"}:
        return "North America"
    if c in {"brazil", "argentina", "chile", "colombia", "peru", "uruguay"}:
        return "South America"
    if c in {"china", "chn", "japan", "jpn", "india", "ind", "singapore", "sgp", "south korea", "korea", "thailand", "vietnam", "malaysia", "indonesia", "philippines"}:
        return "Asia"
    if c in {"united arab emirates", "uae", "saudi arabia", "qatar", "kuwait", "bahrain", "oman", "turkey", "türkiye", "turkiye", "israel", "jordan"}:
        return "Middle East"
    if c in {"south africa", "kenya", "nigeria", "egypt", "morocco", "ghana", "ethiopia", "tanzania", "uganda"}:
        return "Africa"
    if c in {"australia", "aus", "new zealand"}:
        return "Oceania"
    if c in {"russia", "russian federation", "rus"}:
        return "Eurasia"
    return "global"


def regional_infrastructure_context(weather_header):
    templates = load_infrastructure_context()
    if not templates:
        return ""

    city, country = _parse_weather_place(weather_header)
    best_name = "generic"
    best_score = -1
    for name, template in templates.items():
        if name == "generic":
            continue
        score = _template_match_score(template, city, country)
        if score > best_score:
            best_name = name
            best_score = score

    if best_score <= 0:
        best_name = "generic"
    return _format_infrastructure_template(best_name, templates.get(best_name, {}))


def regional_regulatory_context(weather_header):
    templates = load_regulatory_context()
    if not templates:
        return ""

    city, country = _parse_weather_place(weather_header)
    best_name = "generic"
    best_score = -1
    for name, template in templates.items():
        if name == "generic":
            continue
        score = _template_match_score(template, city, country)
        if score > best_score:
            best_name = name
            best_score = score

    if best_score <= 0:
        best_name = "generic"
    formatted = _format_infrastructure_template(best_name, templates.get(best_name, {}))
    return formatted.replace("Regional infrastructure baseline:", "Regional regulatory baseline:")


CEA_USE_TYPE_MAP = {
    # Residential
    "MULTI_RES": "residential", "SINGLE_RES": "residential", "RESIDENTIAL": "residential",
    # Commercial
    "OFFICE": "commercial", "RETAIL": "commercial", "HOTEL": "commercial",
    "RESTAURANT": "commercial", "FOODSTORE": "commercial", "SUPERMARKET": "commercial",
    "LIBRARY": "commercial", "MUSEUM": "commercial", "GYM": "commercial",
    "SWIMMING": "commercial", "CINEMA": "commercial", "COMMERCE": "commercial",
    # Public / institutional
    "HOSPITAL": "public", "SCHOOL": "public", "UNIVERSITY": "public",
    "GOVERNMENT": "public", "POLICE": "public", "FIRE": "public",
    "COMMUNITY": "public", "RELIGION": "public",
    # Industrial
    "INDUSTRIAL": "industrial", "WAREHOUSE": "industrial", "LOGISTICS": "industrial",
    "WORKSHOP": "industrial",
    # Parking / unclear — leave as mixed
    "PARKING": "mixed",
}


def detect_building_use_types(cea_data, selected_buildings=None):
    """
    Read use type columns from zone_geometry.csv (from zone.dbf).
    Returns a dict: {use_category: fraction} e.g. {'commercial': 0.7, 'residential': 0.3}
    and a dominant category string.
    """
    zone_df = (cea_data.get("files") or {}).get("zone_geometry.csv")
    if zone_df is None:
        return None, None

    if selected_buildings:
        name_col = _find_metric_col(zone_df, "name", "building")
        if name_col:
            zone_df = zone_df[zone_df[name_col].isin(selected_buildings)]

    if zone_df.empty:
        return None, None

    # CEA4 use type columns: use1, use1r (ratio), use2, use2r, use3, use3r
    # Also REFERENCE (typology code like "MULTI_RES_1980")
    use_col_pairs = [
        (_find_metric_col(zone_df, "use1", "use_1"), _find_metric_col(zone_df, "use1r", "use_1r")),
        (_find_metric_col(zone_df, "use2", "use_2"), _find_metric_col(zone_df, "use2r", "use_2r")),
        (_find_metric_col(zone_df, "use3", "use_3"), _find_metric_col(zone_df, "use3r", "use_3r")),
    ]

    category_weights = {}
    found_any = False

    for use_col, ratio_col in use_col_pairs:
        if not use_col:
            continue
        for _, row in zone_df.iterrows():
            raw = str(row.get(use_col, "") or "").strip().upper()
            if not raw:
                continue
            # Try matching known codes; also try REFERENCE prefix (e.g. "MULTI_RES_1980_SFH")
            category = CEA_USE_TYPE_MAP.get(raw)
            if not category:
                for code, cat in CEA_USE_TYPE_MAP.items():
                    if raw.startswith(code):
                        category = cat
                        break
            if not category:
                continue
            found_any = True
            ratio = 1.0
            if ratio_col and ratio_col in zone_df.columns:
                try:
                    ratio = float(row.get(ratio_col, 1.0) or 1.0)
                except (ValueError, TypeError):
                    ratio = 1.0
            category_weights[category] = category_weights.get(category, 0.0) + ratio

    # Also try REFERENCE column as a fallback
    ref_col = _find_metric_col(zone_df, "REFERENCE", "reference", "typology")
    if ref_col and not found_any:
        for _, row in zone_df.iterrows():
            raw = str(row.get(ref_col, "") or "").strip().upper()
            for code, cat in CEA_USE_TYPE_MAP.items():
                if raw.startswith(code):
                    category_weights[cat] = category_weights.get(cat, 0.0) + 1.0
                    found_any = True
                    break

    if not found_any or not category_weights:
        return None, None

    total = sum(category_weights.values())
    fractions = {k: round(v / total, 2) for k, v in category_weights.items()}
    dominant = max(fractions, key=fractions.get)
    return fractions, dominant


def regional_economic_context(weather_header, cea_data=None, selected_buildings=None):
    """Return hardcoded economic baseline for the project location and building use type."""
    best_name, t = _select_economic_template(weather_header)
    if not t:
        return ""

    # Detect building use type from zone_geometry if cea_data provided
    use_fractions, dominant_use = None, None
    if cea_data is not None:
        use_fractions, dominant_use = detect_building_use_types(cea_data, selected_buildings)

    currency = t.get("currency", "EUR")
    sym = t.get("currency_symbol", "€")

    def fmt_price(val):
        if val is None:
            return "not hardcoded"
        return f"{sym} {val:.2f}"

    lines = [f"Hardcoded regional economic baseline: {best_name.replace('_', ' ').title()}"]
    lines.append(f"Local currency: {currency} ({sym})")
    lines.append(f"IMPORTANT: All prices below are already in {currency}. Do NOT convert them or express them in EUR/USD unless the user asks for a comparison. Use {sym} symbol throughout the response.")

    # Use type detection result
    use_type_data = t.get("electricity_by_use_type", {})
    if use_fractions and dominant_use and use_type_data:
        use_summary = ", ".join(f"{cat} {int(frac*100)}%" for cat, frac in sorted(use_fractions.items(), key=lambda x: -x[1]))
        lines.append(f"Building use type (from zone_geometry.csv): {use_summary}")
        lines.append(f"Dominant use type: {dominant_use}")
        # Use the dominant use type price
        use_entry = use_type_data.get(dominant_use, {})
        elec = use_entry.get("price")
        elec_lo = use_entry.get("range_low")
        elec_hi = use_entry.get("range_high")
        elec_note = use_entry.get("note", "")
        if elec is not None:
            range_str = f" (range {sym} {elec_lo:.2f}–{sym} {elec_hi:.2f}/kWh)" if elec_lo and elec_hi else ""
            lines.append(f"Electricity price for {dominant_use} use: {sym} {elec:.2f}/kWh{range_str}")
            lines.append(f"Tariff note: {elec_note}")
        # If mixed use, show all relevant prices
        if len(use_fractions) > 1:
            lines.append("Per-use-type electricity prices (for mixed-use payback calculation):")
            for cat, frac in sorted(use_fractions.items(), key=lambda x: -x[1]):
                entry = use_type_data.get(cat, {})
                p = entry.get("price")
                if p is not None:
                    lines.append(f"  {cat} ({int(frac*100)}% of building): {sym} {p:.2f}/kWh — {entry.get('note','')}")
        use_type_note = t.get("use_type_tariff_note", "")
        if use_type_note:
            lines.append(f"Use type tariff context: {use_type_note}")
    else:
        # No use type detected — fall back to showing all categories
        if use_type_data and any(v.get("price") is not None for v in use_type_data.values()):
            lines.append("Building use type: not detected from zone_geometry.csv — showing all tariff categories below.")
            lines.append("Use the building programme description to select the most relevant tariff category:")
            for cat, entry in use_type_data.items():
                p = entry.get("price")
                lo = entry.get("range_low")
                hi = entry.get("range_high")
                if p is not None:
                    range_str = f" (range {sym} {lo:.2f}–{sym} {hi:.2f}/kWh)" if lo and hi else ""
                    lines.append(f"  {cat}: {sym} {p:.2f}/kWh{range_str} — {entry.get('note','')}")
            use_type_note = t.get("use_type_tariff_note", "")
            if use_type_note:
                lines.append(f"Use type tariff context: {use_type_note}")
        else:
            # generic fallback
            elec = t.get("electricity_price_kwh")
            elec_lo = t.get("electricity_price_range_low")
            elec_hi = t.get("electricity_price_range_high")
            if elec is not None:
                range_str = f" (range {sym} {elec_lo:.2f}–{sym} {elec_hi:.2f}/kWh)" if elec_lo and elec_hi else ""
                lines.append(f"Electricity price: {sym} {elec:.2f}/kWh{range_str}")
            lines.append(f"Electricity price note: {t.get('electricity_price_note', '')}")
    lines.append(f"Electricity price trend: {t.get('electricity_price_trend', 'unknown')}")

    exp = t.get("export_compensation_kwh")
    exp_lo = t.get("export_compensation_range_low")
    exp_hi = t.get("export_compensation_range_high")
    if exp is not None:
        range_str = f" (range {sym} {exp_lo:.2f}–{sym} {exp_hi:.2f}/kWh)" if exp_lo and exp_hi else ""
        lines.append(f"Export/feed-in compensation: {sym} {exp:.2f}/kWh{range_str}")
    lines.append(f"Export compensation note: {t.get('export_compensation_note', '')}")

    cost_f_lo = t.get("bipv_cost_facade_m2_low")
    cost_f_hi = t.get("bipv_cost_facade_m2_high")
    cost_r_lo = t.get("bipv_cost_roof_m2_low")
    cost_r_hi = t.get("bipv_cost_roof_m2_high")
    if cost_f_lo and cost_f_hi:
        lines.append(f"BIPV installed cost — facade: {sym} {cost_f_lo}–{sym} {cost_f_hi}/m²")
    if cost_r_lo and cost_r_hi:
        lines.append(f"BIPV installed cost — roof: {sym} {cost_r_lo}–{sym} {cost_r_hi}/m²")
    lines.append(f"BIPV cost note: {t.get('bipv_cost_note', '')}")

    pb_lo = t.get("payback_years_low")
    pb_hi = t.get("payback_years_high")
    if pb_lo and pb_hi:
        lines.append(f"Typical simple payback: {pb_lo}–{pb_hi} years")
    lines.append(f"Payback note: {t.get('payback_note', '')}")

    gc = t.get("grid_carbon_kgco2_kwh")
    if gc is not None:
        lines.append(f"Grid carbon intensity: {gc:.3f} kgCO₂/kWh")
    lines.append(f"Grid carbon note: {t.get('grid_carbon_note', '')}")

    lines.append(f"Overall economic signal: {t.get('economic_signal', 'unknown')}")
    lines.append(f"Primary BIPV argument for this location: {t.get('primary_argument', 'unknown')}")

    incentives = t.get("incentives", [])
    if incentives:
        lines.append("Known incentives and schemes:")
        for inc in incentives:
            lines.append(f"- {inc}")

    precision = t.get("precision_note", "")
    if precision:
        lines.append(f"Precision note (use this instead of generic ElCom/consultant boilerplate): {precision}")

    lines.append(f"Currency enforcement rule: Every price, cost, and tariff in your response MUST use {currency} ({sym}). If a web search result returns a value in EUR or USD, convert it to {currency} using approximate current exchange rates before presenting it. Never show EUR or USD values to the user without first converting to {currency}.")

    return "\n".join(lines)


def build_threshold_economic_inputs(weather_header, cea_data):
    """Prepare local, panel-aware economics for the PV radiation-threshold check."""
    _, t = _select_economic_template(weather_header)
    t = t or {}
    pv_config = (cea_data or {}).get("pv_config", {}) or {}
    files = (cea_data or {}).get("files", {}) or {}

    currency = t.get("currency", "USD")
    sym = t.get("currency_symbol", "$")

    use_fractions, dominant_use = detect_building_use_types(cea_data)
    use_prices = t.get("electricity_by_use_type", {}) or {}
    electricity_price = None
    if use_fractions and use_prices:
        weighted = 0.0
        weight = 0.0
        for category, fraction in use_fractions.items():
            price = use_prices.get(category, {}).get("price")
            if price is not None:
                weighted += float(price) * float(fraction)
                weight += float(fraction)
        if weight > 0:
            electricity_price = weighted / weight
    if electricity_price is None and dominant_use and use_prices.get(dominant_use, {}).get("price") is not None:
        electricity_price = float(use_prices[dominant_use]["price"])
    if electricity_price is None:
        electricity_price = t.get("electricity_price_kwh")

    def midpoint(low_key, high_key, fallback=None):
        low = t.get(low_key)
        high = t.get(high_key)
        if low is not None and high is not None:
            return (float(low) + float(high)) / 2
        return fallback

    pv_areas_by_panel = {}
    pv_performance_by_panel = {}
    for ptype in ["PV1", "PV2", "PV3", "PV4"]:
        df = files.get(f"PV_{ptype}_total_buildings.csv")
        total_df = files.get(f"PV_{ptype}_total.csv")
        roof_area = 0.0
        facade_area = 0.0
        annual_gen = 0.0
        if df is not None and not df.empty:
            for col in df.columns:
                low = col.lower()
                try:
                    value = float(df[col].sum())
                except Exception:
                    continue
                if "pv_roofs" in low and low.endswith("_m2"):
                    roof_area += value
                elif "pv_walls" in low and low.endswith("_m2"):
                    facade_area += value
                elif annual_gen == 0 and ("e_pv_gen" in low or low.startswith("e_pv")):
                    annual_gen = value
        if total_df is not None and not total_df.empty:
            gen_col = next((c for c in total_df.columns if "E_PV_gen" in c or "E_PV" in c), None)
            if gen_col:
                try:
                    annual_gen = float(total_df[gen_col].sum())
                except Exception:
                    pass
        pv_areas_by_panel[ptype] = {"roof_m2": roof_area, "facade_m2": facade_area}
        pv_performance_by_panel[ptype] = {
            "annual_generation_kwh": annual_gen,
            "area_m2": roof_area + facade_area,
        }

    return {
        "pv_types": pv_config.get("pv_types") or [p for p in ["PV1", "PV2", "PV3", "PV4"] if f"PV_{p}_total.csv" in files],
        "panel_on_roof": pv_config.get("panel_on_roof"),
        "panel_on_wall": pv_config.get("panel_on_wall"),
        "pv_areas_by_panel": pv_areas_by_panel,
        "pv_performance_by_panel": pv_performance_by_panel,
        "annual_ghi_kwh_m2": files.get("weather_annual_ghi_kwh_m2"),
        "currency": "EUR",
        "currency_symbol": "€",
        "electricity_price_kwh": electricity_price,
        "export_compensation_kwh": t.get("export_compensation_kwh"),
        "roof_cost_m2": 254.7,
        "facade_cost_m2": 345.7,
        "performance_ratio": 0.75,
        "lifetime_years": 25,
        "discount_rate": 0.05,
        "fixed_om_rate": 0.01,
        "variable_om_per_kwh": 0.0,
    }


@st.cache_data(ttl=86400, show_spinner=False)
def research_public_grid_context(weather_header, skill_id):
    if skill_id != "site-potential--contextual-feasibility--infrastructure-readiness":
        return ""

    city_clean, country = _parse_weather_place(weather_header)
    place = " ".join(p for p in [city_clean, country if country != "-" else ""] if p).strip()
    if not place:
        place = country if country and country != "-" else "project location"
    country_place = country if country and country != "-" else ""
    broad_place = _fallback_region_for_country(country_place)
    query_groups = [
        (
            "local / city-level search",
            [
                f"{place} photovoltaic grid connection export limit utility",
                f"{place} solar PV feed-in tariff grid connection",
                f"{place} distribution grid operator photovoltaic connection transformer capacity",
            ],
        )
    ]
    if country_place:
        query_groups.append((
            "national / country-level fallback",
            [
                f"{country_place} photovoltaic grid connection export limit utility",
                f"{country_place} solar PV feed-in tariff grid connection",
                f"{country_place} distribution grid operator photovoltaic transformer capacity",
            ],
        ))
    query_groups.append((
        "regional / continental fallback",
        [
            f"{broad_place} photovoltaic grid connection export limits distributed solar",
            f"{broad_place} rooftop solar export limit distribution grid transformer capacity",
            f"{broad_place} solar PV feed-in tariff grid connection rules",
        ],
    ))
    query_groups.append((
        "industry-average fallback",
        [
            "distributed solar grid connection export limit transformer capacity industry guidance",
            "rooftop solar PV export constraints self-consumption storage grid connection guidance",
            "BIPV grid connection export limitation transformer capacity design guidance",
        ],
    ))

    seen = set()
    source_lines = []
    used_levels = []
    for level, queries in query_groups:
        candidates = []
        for query in queries:
            for result in _search_duckduckgo(query, max_results=4):
                url = result["url"]
                host = urlparse(url).netloc.lower()
                if url in seen or any(bad in host for bad in ["facebook", "linkedin", "youtube", "instagram"]):
                    continue
                seen.add(url)
                result["query"] = query
                result["level"] = level
                result["score"] = _official_source_score(url)
                candidates.append(result)

        candidates = sorted(candidates, key=lambda r: r["score"], reverse=True)[:5]
        for result in candidates:
            summary = _fetch_public_grid_page_summary(result["url"])
            if not summary:
                continue
            source_lines.append(
                f"- [{result['level']}] {result['title'] or urlparse(result['url']).netloc} ({result['url']}): {summary}"
            )
            if result["level"] not in used_levels:
                used_levels.append(result["level"])
            if len(source_lines) >= 3:
                break
        if source_lines:
            break

    if not source_lines:
        return ""

    return "\n".join([
        "Public grid / utility context found by lightweight web research:",
        f"Search location: {place}",
        f"Search scale used: {', '.join(used_levels) if used_levels else 'none'}",
        *source_lines,
        "Use these sources only for current public context. Label whether each useful fact is local, national, regional/continental, or industry-average. Do not infer exact transformer spare capacity or export cap unless a source explicitly states it.",
    ])


@st.cache_data(ttl=86400, show_spinner=False)
def research_public_contextual_feasibility(weather_header, skill_id):
    if skill_id not in (
        "site-potential--contextual-feasibility--regulatory-constraints",
        "site-potential--contextual-feasibility--basic-economic-signal",
    ):
        return ""

    city_clean, country = _parse_weather_place(weather_header)
    place = " ".join(p for p in [city_clean, country if country != "-" else ""] if p).strip()
    if not place:
        place = country if country and country != "-" else "project location"

    if skill_id == "site-potential--contextual-feasibility--regulatory-constraints":
        label = "Public planning / regulatory context found by lightweight web research:"
        local_place = place
        country_place = country if country and country != "-" else ""
        broad_place = _fallback_region_for_country(country_place)
        query_groups = [
            (
                "local / city-level search",
                [
                    f"{local_place} photovoltaic facade building permit planning permission",
                    f"{local_place} solar panels building regulations heritage conservation area",
                    f"{local_place} building height limit zoning photovoltaic roof solar",
                    f"{local_place} zoning building height limit roof equipment photovoltaic",
                    f"{local_place} mandatory solar photovoltaic new buildings building code",
                    f"{local_place} BIPV facade roof permit local planning authority",
                ],
            )
        ]
        if country_place:
            query_groups.append((
                "national / country-level fallback",
                [
                    f"{country_place} photovoltaic facade building permit planning permission",
                    f"{country_place} solar panels building regulations heritage conservation area",
                    f"{country_place} building height limit zoning photovoltaic roof solar",
                    f"{country_place} mandatory solar photovoltaic new buildings building code",
                    f"{country_place} BIPV facade roof permit building regulations",
                ],
            ))
        query_groups.append((
            "regional / continental fallback",
            [
                f"{broad_place} photovoltaic building regulations facade roof planning permission",
                f"{broad_place} solar panels heritage conservation building height roof equipment",
                f"{broad_place} BIPV facade regulations reflectivity glare building permit",
            ],
        ))
        query_groups.append((
            "industry-average fallback",
            [
                "BIPV facade roof planning constraints height heritage reflectivity industry guidance",
                "building integrated photovoltaics regulatory constraints facade roof heritage height guidance",
                "BIPV design guide planning permission facade roof reflectivity glare height constraints",
            ],
        ))
        keywords = [
            "photovoltaic", "solar", "bipv", "building permit", "planning",
            "permission", "heritage", "conservation", "facade", "façade",
            "roof", "building code", "mandatory", "requirement", "regulation",
            "authority", "zoning", "height limit", "building height", "roof equipment",
            "reflectivity", "glare", "material",
        ]
        closing_rule = (
            "Use these sources only for public planning context. Label whether each useful fact is local, national, regional/continental, or industry-average. Do not infer exact parcel heritage/conservation status, "
            "height-zone status, roof-equipment height treatment, permit outcome, or mandatory coverage unless a source explicitly states it."
        )
    else:
        label = "Public market / economic context found by lightweight web research:"
        country_place = country if country and country != "-" else ""
        broad_place = _fallback_region_for_country(country_place)
        query_groups = [
            (
                "local / city-level search",
                [
                    f"{place} electricity tariff commercial residential kWh official",
                    f"{place} solar PV feed-in tariff export compensation official",
                    f"{place} grid carbon intensity electricity official",
                    f"{place} BIPV installation cost per m2 payback solar",
                ],
            )
        ]
        if country_place:
            query_groups.append((
                "national / country-level fallback",
                [
                    f"{country_place} electricity tariff commercial residential kWh official",
                    f"{country_place} solar PV feed-in tariff export compensation official",
                    f"{country_place} grid carbon intensity electricity official",
                    f"{country_place} BIPV installation cost per m2 payback solar",
                ],
            ))
        query_groups.append((
            "regional / continental fallback",
            [
                f"{broad_place} BIPV installation cost per m2 payback solar",
                f"{broad_place} solar PV economics electricity tariffs grid carbon intensity",
                f"{broad_place} feed-in tariff export compensation solar PV",
            ],
        ))
        query_groups.append((
            "industry-average fallback",
            [
                "BIPV installation cost per m2 facade roof industry average",
                "building integrated photovoltaics payback cost per m2 industry average",
                "IEA solar PV economics grid carbon intensity electricity industry benchmark",
            ],
        ))
        keywords = [
            "electricity", "tariff", "price", "kwh", "commercial", "residential",
            "feed-in", "feed in", "export", "compensation", "remuneration",
            "grid carbon", "carbon intensity", "emission factor", "co2",
            "installation cost", "bipv", "photovoltaic", "solar", "payback",
            "subsidy", "incentive", "rebate", "net metering",
        ]
        closing_rule = (
            "Use these sources only for public economic context. Label whether each useful fact is local, national, regional/continental, or industry-average. Do not infer exact project tariff, export value, "
            "BIPV cost, subsidy eligibility, or payback unless a source explicitly states it."
        )

    seen = set()
    candidates = []
    source_lines = []
    used_levels = []
    for level, queries in query_groups:
        candidates = []
        for query in queries:
            for result in _search_duckduckgo(query, max_results=4):
                url = result["url"]
                host = urlparse(url).netloc.lower()
                if url in seen or any(bad in host for bad in ["facebook", "linkedin", "youtube", "instagram"]):
                    continue
                seen.add(url)
                result["query"] = query
                result["level"] = level
                result["score"] = _official_source_score(url)
                candidates.append(result)

        candidates = sorted(candidates, key=lambda r: r["score"], reverse=True)[:5]
        for result in candidates:
            summary = _fetch_public_page_summary(result["url"], keywords=keywords)
            if not summary:
                continue
            source_lines.append(
                f"- [{result['level']}] {result['title'] or urlparse(result['url']).netloc} ({result['url']}): {summary}"
            )
            if result["level"] not in used_levels:
                used_levels.append(result["level"])
            if len(source_lines) >= 3:
                break
        if source_lines:
            break

    if not source_lines:
        return ""

    return "\n".join([
        label,
        f"Search location: {place}",
        f"Search scale used: {', '.join(used_levels) if used_levels else 'none'}",
        *source_lines,
        closing_rule,
    ])


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
This mode must stand alone, but it should NOT repeat the full numeric breakdown or detailed design recipe from the other modes.
- 2-3 bullet points maximum.
- Use formal, professional, non-expert language. Avoid specialist terminology unless it is necessary.
- Lead with the design decision and priority order.
- Include only the one or two most important numbers that support the decision.
- Explain in plain language what the number means for the architect.
- End with one concrete "For BIPV," action with a real number or spatial allowance where available.
- No methodology, no full evidence list, no detailed staging recipe, no benchmarks — just the decision and priorities.""",

        "Explain the numbers": """OUTPUT MODE: Explain the numbers
The evidence and terminology layer. This mode must stand alone, but it should NOT repeat the concise decision wording from Key takeaway or the full action recipe from Design implication.
Cover all of the following:
- What each key number is and where it comes from.
- What it means in context — compare to benchmarks, thresholds, or industry norms where relevant.
- How the numbers relate to each other (e.g. generation vs demand, embodied vs operational carbon).
- Keep the correct technical terminology (e.g. peak demand, PV peak, export pressure, transformer screening, self-consumption, annual coverage), but define each term in simple words the first time it appears.
- Use bullet points, one point per number or comparison.
- Include the actual values — do not be vague.
- Keep design recommendations brief: only state what each number controls architecturally, not the full design recipe.
- This mode is paired with charts generated by the app — do not describe charts, but you may reference what the architect should look for in them.""",

        "Design implication": """OUTPUT MODE: Design implication
A practical recipe for the architect based on the results. This mode must stand alone, but it should NOT re-explain every number from Explain the numbers.
No charts.
- 3-5 bullet points, each a specific, actionable design suggestion.
- Every bullet must follow directly from the data — no generic advice.
- Include numbers where they sharpen the recommendation (e.g. area, ratio, orientation).
- Frame each point as: what to do, and why the data supports it.
- Focus on actions, spatial allowances, phasing, placement, and design options.
- Do not explain what the numbers are — use only the minimum number needed to justify the action."""
    }

    if skill_id == "site-potential--contextual-feasibility--regulatory-constraints":
        mode_block = """OUTPUT MODE: Regulatory brief
Regulatory Constraints is a single-output endpoint. Do not split the answer into Key takeaway, Explain the numbers, and Design implication.
- Give one concise regulatory brief for early BIPV design.
- Start with the overall stance: Permissive, Moderate, Restrictive, or Unknown / needs local confirmation.
- Include only the rules or constraints supported by supplied public context or computed project data.
- Use local facts first; if only national, regional, or industry-average guidance is supplied, label that scale clearly.
- Include source website addresses for the public facts used.
- Convert the regulatory context into a clear design consequence: what to change, reserve, avoid, document, or verify now.
- If exact parcel-specific information is missing, add one short precision note naming who to contact and exactly what to ask. Do not let the whole answer become a caveat."""
    elif skill_id == "optimize-my-design--design-integration-recipe":
        mode_block = """OUTPUT MODE: Design recipe
Design Integration Recipe is a single-output endpoint. Do not split the answer into Key takeaway, Explain the numbers, and Design implication.
- Produce one coherent project guide, not a summary of separate analyses.
- Start with the final recommended BIPV concept in plain professional language.
- Then give the recipe in sections: PV placement, panel/envelope strategy, storage/grid/space allowance, client/carbon argument, and next design moves.
- Use prior analyses already run in the session as the main interpretation memory.
- Use computed project facts only to support the recipe or fill gaps. Clearly mark missing confidence gaps.
- Do not repeat every number. Use the few numbers that change the design decision.
- Distinguish physical roof/facade area from CEA simulated active PV module area.
- End with concrete architectural actions, not generic advice."""
    elif skill_id in (
        "performance-estimation--panel-type-tradeoff",
        "optimize-my-design--panel-type-tradeoff",
    ) and output_mode == "Explain the numbers":
        mode_block = """OUTPUT MODE: Explain the numbers
Return one compact markdown table first. Columns: panel type, technology, generation (kWh/year), area (m2), yield (kWh/m2/year), efficiency (%), embodied carbon (kgCO2/m2), roof cost (€/m2), facade cost (€/m2).
After the table, add at most three short bullets:
- which panel produces the most total generation,
- which panel has the lowest embodied carbon,
- what the main design trade-off is.
Do not write one paragraph per panel. Do not use "currency/m2"; panel database costs are in euros, so label them as €/m2."""
    else:
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
        area_lines = compute_building_surface_area_screen(cea_data, selected_buildings)
        if area_lines:
            compact_metrics = "\n".join([
                compact_metrics,
                "",
                "Physical envelope area context:",
                *area_lines,
            ])
        public_context = ""
        if skill_id in (
            "site-potential--contextual-feasibility--infrastructure-readiness",
            "site-potential--contextual-feasibility--regulatory-constraints",
            "site-potential--contextual-feasibility--basic-economic-signal",
        ):
            weather_header = (cea_data.get("files", {}) or {}).get("weather_header", "")
            if skill_id == "site-potential--contextual-feasibility--infrastructure-readiness":
                context_parts = [
                    regional_infrastructure_context(weather_header),
                    research_public_grid_context(weather_header, skill_id),
                ]
            elif skill_id == "site-potential--contextual-feasibility--regulatory-constraints":
                context_parts = [
                    regional_regulatory_context(weather_header),
                    research_public_contextual_feasibility(weather_header, skill_id),
                ]
            else:
                context_parts = [
                    regional_economic_context(weather_header, cea_data=cea_data, selected_buildings=selected_buildings),
                    research_public_contextual_feasibility(weather_header, skill_id),
                ]
            public_context = "\n\n".join(part for part in context_parts if part)
        public_context_block = f"\n## Public context research\n{public_context}\n" if public_context else ""
        return f"""You are a BIPV expert helping architects interpret CEA4 simulation results.
Scale: {scale}{building_context}

{mode_block}

## Skill task
{COMPACT_SKILL_TASKS[skill_id]}

## Computed metrics
{compact_metrics}
{public_context_block}

Use only the computed metrics and supplied public research above. Do not invent missing values, sources, tariffs, regulations, transformer capacity, export caps, or file contents. If exact public grid values are not supplied, do not pretend they are known; use the CEA/project evidence and public context to give concept-stage choices, then add a short precision note only if useful.
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
    threshold_details = threshold_result.get("threshold_details_by_panel", {})
    cea_reference = threshold_result.get("cea_reference_threshold", 800)
    iteration_thresholds = threshold_result.get("cea_iteration_thresholds", [0, 200, 400, 600, 800])

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

    recommended_panel = threshold_result.get("recommended_panel") or run_pv_types[0]
    recommended = threshold_result.get("recommended_threshold") or cea_reference
    recommended_detail = threshold_details.get(recommended_panel, {})
    threshold_basis = threshold_result.get("threshold_basis", "carbon_parity")
    fallback_reason = threshold_result.get("fallback_reason")
    fallback_limit = threshold_result.get("facade_empty_risk_threshold", 800)
    solar_band = threshold_result.get("solar_resource_benchmark", {})
    band_lower = solar_band.get("lower", 500)
    band_upper = solar_band.get("upper", fallback_limit)
    annual_ghi = solar_band.get("annual_ghi_kwh_m2")

    if len(run_pv_types) == 1:
        sim_label = f'Photovoltaic simulation<br><span style="font-size:11px;color:#999;">{run_pv_types[0]} — {PV_PANEL_TYPES.get(run_pv_types[0], {}).get("description", "")}</span>'
    else:
        types_str = ", ".join([f"{p} ({PV_PANEL_TYPES.get(p,{}).get('description','')})" for p in run_pv_types])
        sim_label = f'Photovoltaic simulation<br><span style="font-size:11px;color:#999;">{types_str}</span>'

    eta = recommended_detail.get("eta")
    pr = recommended_detail.get("performance_ratio", 0.75)
    em_bipv = recommended_detail.get("em_bipv")
    lifetime = recommended_detail.get("lifetime_years", 25)
    cpp10 = recommended_detail.get("carbon_payback_10yr_threshold")
    carbon_parity = recommended_detail.get("carbon_parity_threshold")
    economic_threshold = recommended_detail.get("economic_threshold")
    if len(run_pv_types) == 1:
        panel_intro = f'This checks <b>{recommended_panel}</b> in {city}, {country}.'
    else:
        panel_intro = f'This first selects the <b>best overall simulated PV option</b>, <b>{recommended_panel}</b>, then checks it for {city}, {country}.'

    is_solar_band_resolution = threshold_basis.startswith("solar_band_")
    is_lcoe_fallback = threshold_basis in ("economic_lcoe_fallback", "economic_lcoe_bounded_fallback") or is_solar_band_resolution

    if is_lcoe_fallback:
        carbon_position = "outside"
        if carbon_parity is not None:
            carbon_position = "below" if carbon_parity < band_lower else "above"
        ghi_text = f" from annual GHI {annual_ghi:,.0f} kWh/m²/year" if annual_ghi else ""
        if threshold_basis == "solar_band_lower_benchmark":
            resolution_note = f' Because at least one threshold falls below the lower benchmark, the displayed value is the lower benchmark.'
        elif threshold_basis == "solar_band_upper_benchmark":
            resolution_note = f' Because both thresholds are above the upper benchmark, the displayed value is the upper benchmark.'
        elif is_solar_band_resolution:
            resolution_note = f' The displayed value follows the solar-resource benchmark resolution rule.'
        else:
            resolution_note = ""
        info_text = (
            f'{panel_intro} Its carbon threshold is {int(carbon_parity)} kWh/m&#x00B2;/year, '
            f'which is {carbon_position} the location-specific solar-resource band '
            f'{int(band_lower)}–{int(band_upper)} kWh/m&#x00B2;/year{ghi_text}. '
            f'The LCOE threshold is {int(economic_threshold)} kWh/m&#x00B2;/year. '
            f'The displayed recommendation is <b>{int(recommended)} kWh/m&#x00B2;/year</b>.{resolution_note}'
        )
    else:
        info_text = (
            f'{panel_intro} The displayed value is its carbon-parity threshold using local grid carbon '
            f'{em_grid:.3f} kgCO&#x2082;/kWh, embodied carbon {em_bipv:.1f} kgCO&#x2082;/m&#x00B2;, '
            f'efficiency {eta:.1%}, PR {pr:.2f}, and {lifetime} years lifetime. '
            f'The stricter 10-year carbon-payback threshold is {int(cpp10)} kWh/m&#x00B2;/year.'
        )

    st.markdown("**Parameter check**")

    h1, h2, h3, h4 = st.columns([2.5, 2, 2, 4])
    for col, label in zip([h1, h2, h3, h4], ["Simulation", "Parameter", "Recommended value", "Info"]):
        with col:
            cost_sentence = (
                'Carbon and LCOE are checked against the local solar-resource benchmark band before showing the final value.<br><br>'
                if is_lcoe_fallback
                else 'Cost/LCOE can be treated in the economic prompts, but it is not used as the main radiation-threshold value here.<br><br>'
            )
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
        tooltip_basis = "solar-band resolved" if is_solar_band_resolution else ("LCOE fallback" if is_lcoe_fallback else "carbon-parity")
        tooltip = f"Calculated {tooltip_basis} threshold for {recommended_panel}; CEA default reference is {int(cea_reference)} kWh/m²/year"
        bg, border = "#f0fff4", "#b2dfdb"
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
                    (lambda d: (
                    f'<tr><td style="padding:2px 8px;">{p}</td>'
                    f'<td style="padding:2px 8px;">{PV_PANEL_TYPES.get(p,{}).get("description","")}</td>'
                    f'<td style="padding:2px 8px;">{d.get("em_bipv",0):,.1f} kgCO&#x2082;/m&#x00B2;</td>'
                    f'<td style="padding:2px 8px;">{d.get("eta",0):.1%}</td>'
                    f'<td style="padding:2px 8px;"><b>{int(d.get("carbon_parity_threshold") or cea_reference)} kWh/m&#x00B2;/yr</b></td>'
                    f'<td style="padding:2px 8px;">{int(d.get("carbon_payback_10yr_threshold") or cea_reference)} kWh/m&#x00B2;/yr</td></tr>'
                    ))(threshold_details.get(p, {}))
                    for p in run_pv_types
                ])
                panel_section = (
                    f'<p style="font-size:12px;margin:8px 0 4px 0;"><strong>Thresholds by panel type:</strong></p>'
                    f'<table style="font-size:11px;color:#555;border-collapse:collapse;">'
                    f'<tr style="color:#999;"><td style="padding:2px 8px;">Type</td><td style="padding:2px 8px;">Technology</td>'
                    f'<td style="padding:2px 8px;">Embodied carbon</td><td style="padding:2px 8px;">Efficiency</td>'
                    f'<td style="padding:2px 8px;">Carbon parity</td><td style="padding:2px 8px;">10yr carbon payback</td></tr>'
                    f'{panel_table}</table>'
                )
            else:
                panel_section = ""

            eta_val = recommended_detail.get("eta", 0)
            pr_val = recommended_detail.get("performance_ratio", 0.75)
            em_val = recommended_detail.get("em_bipv", 0)
            lifetime_val = recommended_detail.get("lifetime_years", 25)
            cpp10_val = recommended_detail.get("carbon_payback_10yr_threshold")
            economic_val = recommended_detail.get("economic_threshold")
            carbon_val = recommended_detail.get("carbon_parity_threshold")
            if is_lcoe_fallback:
                carbon_position = "below" if carbon_val < band_lower else "above"
                ghi_text = f" Annual GHI from the weather file is {annual_ghi:,.0f} kWh/m&sup2;/year." if annual_ghi else ""
                if threshold_basis == "solar_band_lower_benchmark":
                    rule_text = "At least one threshold is below the lower benchmark, so the lower benchmark is used."
                elif threshold_basis == "solar_band_upper_benchmark":
                    rule_text = "Both thresholds are above the upper benchmark, so the upper benchmark is used."
                elif is_solar_band_resolution:
                    rule_text = "One threshold sits inside the benchmark band, so that value is used."
                else:
                    rule_text = "The LCOE fallback value is used."
                threshold_explanation = (
                    f'<strong>Best overall PV option:</strong> {recommended_panel}. '
                    f'Its carbon-parity threshold is <strong>{int(carbon_val)} kWh/m&sup2;/year</strong>, '
                    f'which is {carbon_position} the location-specific solar-resource benchmark band '
                    f'<strong>{int(band_lower)}–{int(band_upper)} kWh/m&sup2;/year</strong>.{ghi_text} '
                    f'Its LCOE threshold is <strong>{int(economic_val)} kWh/m&sup2;/year</strong>. '
                    f'{rule_text} Final displayed value: <strong>{int(recommended)} kWh/m&sup2;/year</strong>.'
                )
            else:
                threshold_explanation = (
                    f'<strong>For {recommended_panel}:</strong> {em_val:.1f} kgCO&#x2082;/m&sup2; / '
                    f'({em_grid:.3f} kgCO&#x2082;/kWh × {eta_val:.1%} × {pr_val:.2f} × {lifetime_val} years) '
                    f'= <strong>{int(recommended)} kWh/m&sup2;/year</strong>.<br>'
                    f'The stricter 10-year carbon-payback target would require '
                    f'<strong>{int(cpp10_val)} kWh/m&sup2;/year</strong>. '
                )
            st.markdown(
                f'<div style="background:#f7f7f7;border:1px solid #e8e8e8;border-radius:8px;'
                f'padding:12px 14px;margin-top:8px;font-size:12px;color:#555;line-height:1.7;">'
                f'Happle et al. define the threshold by comparing PV life-cycle carbon intensity with the local grid. '
                f'McCarty et al. show that this threshold changes strongly by grid carbon intensity and PV technology; '
                f'cost/LCOE is a separate economic target. The app first checks whether the carbon result sits inside the '
                f'location-specific solar-resource band, then falls back to LCOE if it does not.<br><br>'
                f'<strong>Formula used for the displayed value:</strong> threshold = embodied carbon / '
                f'(grid carbon × efficiency × PR × lifetime).<br>'
                f'{threshold_explanation}<br>'
                f'{cost_sentence}'
                f'CEA still recommends sensitivity testing around '
                f'<strong>{", ".join(str(x) for x in iteration_thresholds)} kWh/m&sup2;/year</strong> when exploring cost/yield trade-offs.'
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

def invalidate_analysis_cache():
    st.session_state.analysis_ran = False
    st.session_state.cached_system_prompt = None

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("cea_data", None), ("chat_history", []),
              ("tree_scale", None), ("tree_goal", None), ("tree_sub", None),
              ("tree_subsub", None), ("tree_mode", None),
              ("skill_id", None), ("skill_name", None),
              ("analysis_ran", False), ("threshold_result", None),
              ("param_check_hidden", False),
              ("selected_building", None), ("selected_cluster", []),
              ("reasoning_open", False), ("reasoning_threshold", False),
              ("cached_system_prompt", None), ("tree_subsubsub", None),
              ("analysis_log", []), ("pv_coverage_scenario", None),
              ("pv_coverage_pct", 50)]:   # FIX 2: cache slot
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
            st.session_state.analysis_log = []
            st.session_state.param_check_hidden = False
            if "weather_header" in cea_data["files"]:
                st.session_state.threshold_result = get_threshold_check(
                    cea_data["files"]["weather_header"], cea_default=800,
                    self_consumption=cea_data.get("pv_config", {}).get("self_consumption", 0.5),
                    acacia_data=load_acacia_curves(),
                    economic_inputs=build_threshold_economic_inputs(cea_data["files"]["weather_header"], cea_data)
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
                        label_visibility="collapsed", key="building_selector",
                        on_change=invalidate_analysis_cache
                    )
                    st.session_state.selected_building = chosen
                elif st.session_state.tree_scale == "Cluster":
                    st.session_state.selected_cluster = [
                        b for b in st.session_state.selected_cluster
                        if b in building_names
                    ]
                    n = len(st.session_state.selected_cluster)
                    selected_label = "No buildings selected yet" if n == 0 else f"{n} building{'s' if n > 1 else ''} selected"
                    st.markdown(
                        f'<div class="cluster-counter">{selected_label}</div>',
                        unsafe_allow_html=True
                    )
                    st.markdown("**Select buildings for cluster**")
                    st.multiselect(
                        "Buildings", building_names,
                        label_visibility="collapsed",
                        key="selected_cluster",
                        on_change=invalidate_analysis_cache
                    )

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
                    "Surface Prioritisation": "Where should I place the panels?",
                    "Envelope Simplification": "What small geometric changes would improve performance?",
                    "Construction & Integration": "How can this be integrated into the building?",
                    "Design Integration Recipe": "What is the full BIPV design recipe based on the analyses already run?",
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
                        "Carbon Footprint": "How much carbon does this building's electricity use create, and how much does BIPV reduce it?",
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
            if st.session_state.skill_id in SINGLE_OUTPUT_SKILLS:
                fixed_mode = SINGLE_OUTPUT_SKILLS[st.session_state.skill_id]
                if st.session_state.tree_mode != fixed_mode:
                    st.session_state.tree_mode = fixed_mode
                    st.session_state.analysis_ran = False
                    st.session_state.cached_system_prompt = None
                    st.rerun()
                st.markdown(f"**Output** · *{fixed_mode}*")
            elif st.session_state.tree_mode:
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
                          "selected_building","selected_cluster","cached_system_prompt","analysis_log",
                          "pv_coverage_scenario","pv_coverage_pct","pv_coverage_pct_widget"]:
                    st.session_state[k] = None if k != "selected_cluster" else []
                st.session_state.analysis_log = []
                st.session_state.pv_coverage_pct = 50
                st.session_state.pv_coverage_pct_widget = 50
                st.session_state.chat_history = []
                st.rerun()

    # ── Analysis section ───────────────────────────────────────────────────────
    st.markdown("---")
    with st.container():
        st.markdown("### Analysis")

        if (st.session_state.analysis_ran
                and st.session_state.skill_id == "optimize-my-design--pv-coverage-scenario"):
            _scale = st.session_state.tree_scale
            _selected = None
            if _scale == "Building" and st.session_state.selected_building:
                _selected = [st.session_state.selected_building]
            elif _scale == "Cluster" and st.session_state.selected_cluster:
                _selected = st.session_state.selected_cluster
            st.markdown("**PV Coverage Scenario**")
            render_pv_coverage_scenario_tool(st.session_state.cea_data, _selected)

        elif st.session_state.analysis_ran and st.session_state.skill_id and not st.session_state.chat_history:
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
            st.session_state.analysis_log.append({
                "skill_id": st.session_state.skill_id,
                "skill_name": st.session_state.skill_name,
                "mode": st.session_state.tree_mode,
                "scale": scale,
                "selected_buildings": selected_buildings or [],
                "response": response,
            })
            st.rerun()

        if (not st.session_state.chat_history
                and st.session_state.skill_id != "optimize-my-design--pv-coverage-scenario"):
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
