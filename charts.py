"""
charts.py — BIPV Analyst chart library
Generates Altair charts from CEA data. Zero LLM calls — all charts are
computed directly from dataframes. Called from app.py after LLM response.
"""
import pandas as pd
import altair as alt
from pathlib import Path

# ── Colour palette ────────────────────────────────────────────────────────────
C_PV       = "#c8a96e"   # warm gold — PV generation
C_DEMAND   = "#2d3142"   # dark navy — demand
C_SURPLUS  = "#7ec8a0"   # soft green — surplus / benefit
C_CARBON   = "#e07b5a"   # terracotta — carbon / cost
C_NEUTRAL  = "#a0a0a0"   # grey — secondary series
C_GRID     = "#e0dcd4"   # light — grid lines
C_SURPLUS_YELLOW = "#f2c94c"  # bright yellow — surplus / export
C_DEFICIT_GREY   = "#8a8f98"  # readable grey — deficit / import

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
          "Jul","Aug","Sep","Oct","Nov","Dec"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _base_theme():
    return {
        "config": {
            "view": {"strokeWidth": 0},
            "axis": {"grid": True, "gridColor": C_GRID, "gridDash": [3, 3],
                     "labelFontSize": 11, "titleFontSize": 12},
            "legend": {"labelFontSize": 11, "titleFontSize": 11},
        }
    }

def _find_col(df, *keywords):
    """Return first column whose name contains any of the keywords."""
    if df is None:
        return None
    for kw in keywords:
        match = next((c for c in df.columns if kw.lower() in c.lower()), None)
        if match:
            return match
    return None


def _num(series):
    """Numeric series with bad/missing values treated as zero."""
    return pd.to_numeric(series, errors="coerce").fillna(0)

def _season_col(df):
    """Return the real season label column, avoiding period_hour metadata."""
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

def _monthly_from_hourly(df, col):
    """Aggregate an hourly dataframe column to monthly totals (MWh)."""
    date_col = _find_col(df, "date", "Date", "DATE", "time", "Time")
    if date_col is None:
        return None
    try:
        df = df.copy()
        df["_dt"] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
        df["month"] = df["_dt"].dt.month
        monthly = df.groupby("month")[col].sum() / 1000  # kWh → MWh
        return monthly.reindex(range(1, 13), fill_value=0)
    except Exception:
        return None


def _pv_surface_generation_rows(cea_data, pv_fname, selected_buildings=None):
    """Return annual PV generation by roof and facade orientation from *_total_buildings.csv."""
    bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
    df_b = cea_data["files"].get(bldg_fname)
    if df_b is None or df_b.empty:
        return []
    df_b = df_b.copy()
    name_col = _find_col(df_b, "name", "Name", "building")
    if selected_buildings and name_col:
        df_b = df_b[df_b[name_col].isin(selected_buildings)]
    if df_b.empty:
        return []

    def energy_col_for(surface_key):
        key = surface_key.lower()
        exact_patterns = {
            "roof": ["pv_roofs_top_e_kwh", "pv_roofs_e_kwh", "roof_e_kwh"],
            "south": ["pv_walls_south_e_kwh", "wall_south_e_kwh", "walls_south_e_kwh"],
            "east": ["pv_walls_east_e_kwh", "wall_east_e_kwh", "walls_east_e_kwh"],
            "west": ["pv_walls_west_e_kwh", "wall_west_e_kwh", "walls_west_e_kwh"],
            "north": ["pv_walls_north_e_kwh", "wall_north_e_kwh", "walls_north_e_kwh"],
        }
        lowered = {c.lower(): c for c in df_b.columns}
        for pattern in exact_patterns[key]:
            if pattern in lowered:
                return lowered[pattern]

        for col in df_b.columns:
            low = col.lower()
            if "m2" in low or "area" in low:
                continue
            if "kwh" not in low and "_e_" not in low and not low.endswith("_e"):
                continue
            if key == "roof" and "roof" in low:
                return col
            if key != "roof" and key in low and ("wall" in low or "facade" in low):
                return col
        return None

    surface_specs = [
        ("Roof", "Roof", "roof"),
        ("Facade", "South facade", "south"),
        ("Facade", "East facade", "east"),
        ("Facade", "West facade", "west"),
        ("Facade", "North facade", "north"),
    ]
    rows = []
    for group, surface, surface_key in surface_specs:
        col = energy_col_for(surface_key)
        if col:
            kwh = pd.to_numeric(df_b[col], errors="coerce").fillna(0).sum()
            if kwh > 0:
                rows.append({"Group": group, "Surface": surface, "kWh": float(kwh), "MWh": float(kwh) / 1000})
    return rows


def _pv_surface_area_rows(cea_data, pv_fname, selected_buildings=None):
    """Return active PV area by roof and facade orientation from *_total_buildings.csv."""
    bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
    df_b = cea_data["files"].get(bldg_fname)
    if df_b is None or df_b.empty:
        return []
    df_b = df_b.copy()
    name_col = _find_col(df_b, "name", "Name", "building")
    if selected_buildings and name_col:
        df_b = df_b[df_b[name_col].isin(selected_buildings)]
    if df_b.empty:
        return []

    def area_col_for(surface_key):
        key = surface_key.lower()
        exact_patterns = {
            "roof": ["pv_roofs_top_m2", "pv_roofs_m2", "roof_m2"],
            "south": ["pv_walls_south_m2", "wall_south_m2", "walls_south_m2"],
            "east": ["pv_walls_east_m2", "wall_east_m2", "walls_east_m2"],
            "west": ["pv_walls_west_m2", "wall_west_m2", "walls_west_m2"],
            "north": ["pv_walls_north_m2", "wall_north_m2", "walls_north_m2"],
        }
        lowered = {c.lower(): c for c in df_b.columns}
        for pattern in exact_patterns[key]:
            if pattern in lowered:
                return lowered[pattern]
        for col in df_b.columns:
            low = col.lower()
            if "m2" not in low:
                continue
            if key == "roof" and "roof" in low:
                return col
            if key != "roof" and key in low and ("wall" in low or "facade" in low):
                return col
        return None

    surface_specs = [
        ("Roof", "Roof", "roof"),
        ("Facade", "South facade", "south"),
        ("Facade", "East facade", "east"),
        ("Facade", "West facade", "west"),
        ("Facade", "North facade", "north"),
    ]
    rows = []
    for group, surface, surface_key in surface_specs:
        col = area_col_for(surface_key)
        if col:
            area = pd.to_numeric(df_b[col], errors="coerce").fillna(0).sum()
            if area > 0:
                rows.append({"Group": group, "Surface": surface, "Area (m2)": float(area)})
    return rows


def _economic_price_for_chart(cea_data):
    """Small local tariff assumption used only for chart estimates."""
    location_text = " ".join(str(v) for v in cea_data.get("files", {}).keys()).lower()
    weather_header = cea_data["files"].get("weather_header.txt")
    if weather_header is not None:
        try:
            location_text += " " + str(weather_header).lower()
        except Exception:
            pass
    if any(token in location_text for token in ["zug", "zurich", "switzerland", "che"]):
        return 0.29, "CHF/kWh"
    return 0.28, "currency/kWh"


def _panel_costs_for_chart(cea_data):
    panel_df = cea_data["files"].get("PHOTOVOLTAIC_PANELS.csv")
    roof_cost = 254.7
    facade_cost = 345.7
    if panel_df is not None and not panel_df.empty:
        try:
            roof_col = _find_col(panel_df, "cost_roof", "roof_cost", "roof")
            facade_col = _find_col(panel_df, "cost_facade", "facade_cost", "facade")
            generic_col = _find_col(panel_df, "cost", "Cost", "CAPEX", "price")
            if roof_col:
                roof_cost = float(panel_df[roof_col].iloc[0])
            elif generic_col:
                roof_cost = float(panel_df[generic_col].iloc[0])
            if facade_col:
                facade_cost = float(panel_df[facade_col].iloc[0])
            elif generic_col:
                facade_cost = float(panel_df[generic_col].iloc[0])
        except Exception:
            pass
    return roof_cost, facade_cost


def _panel_embodied_carbon_kg_m2(cea_data):
    panel_df = cea_data["files"].get("PHOTOVOLTAIC_PANELS.csv")
    embodied = 329.0
    if panel_df is not None and not panel_df.empty:
        em_col = _find_col(panel_df, "CO2", "embodied", "carbon", "GHG")
        if em_col:
            try:
                embodied = float(panel_df[em_col].iloc[0])
            except Exception:
                pass
    return embodied


def _pv_surface_pie_chart(cea_data, pv_fname, selected_buildings=None):
    rows = _pv_surface_generation_rows(cea_data, pv_fname, selected_buildings)
    if not rows:
        return None
    df_surface = pd.DataFrame(rows)
    total_mwh = float(df_surface["MWh"].sum())
    if total_mwh <= 0:
        return None

    df_group = df_surface.groupby("Group", as_index=False)["MWh"].sum()
    df_group["Share"] = df_group["MWh"] / total_mwh
    roof_mwh = float(df_group.loc[df_group["Group"] == "Roof", "MWh"].sum())
    facade_mwh = float(df_group.loc[df_group["Group"] == "Facade", "MWh"].sum())

    group_pie = alt.Chart(df_group).mark_arc(outerRadius=92, innerRadius=34).encode(
        theta=alt.Theta("MWh:Q"),
        color=alt.Color(
            "Group:N",
            scale=alt.Scale(domain=["Roof", "Facade"], range=[C_PV, C_SURPLUS]),
            legend=alt.Legend(title="PV yield")
        ),
        tooltip=[
            alt.Tooltip("Group:N"),
            alt.Tooltip("MWh:Q", title="MWh/year", format=",.1f"),
            alt.Tooltip("Share:Q", title="Share", format=".1%")
        ]
    ).properties(
        title=f"Roof vs facade PV yield — Total: {total_mwh:,.1f} MWh/year",
        width=330,
        height=270
    )

    df_facade = df_surface[df_surface["Group"] == "Facade"].copy()
    if df_facade.empty or facade_mwh <= 0:
        return group_pie
    df_facade["Share"] = df_facade["MWh"] / facade_mwh
    facade_order = ["South facade", "East facade", "West facade", "North facade"]
    facade_pie = alt.Chart(df_facade).mark_arc(outerRadius=92, innerRadius=34).encode(
        theta=alt.Theta("MWh:Q"),
        color=alt.Color(
            "Surface:N",
            scale=alt.Scale(domain=facade_order, range=[C_SURPLUS, "#e8b86d", "#a8d5b5", C_NEUTRAL]),
            legend=alt.Legend(title="Facade yield")
        ),
        tooltip=[
            alt.Tooltip("Surface:N"),
            alt.Tooltip("MWh:Q", title="MWh/year", format=",.1f"),
            alt.Tooltip("Share:Q", title="Facade share", format=".1%")
        ]
    ).properties(title="Facade yield distribution", width=330, height=270)

    return alt.hconcat(group_pie, facade_pie, spacing=28).resolve_scale(color="independent")


# ── Chart builders ────────────────────────────────────────────────────────────

def _height_col(df):
    return _find_col(df, "height_ag", "height", "floors_ag", "floors")

def _height_series(df, col):
    if col is None or col not in df.columns:
        return pd.Series([1] * len(df), index=df.index)
    values = pd.to_numeric(df[col], errors="coerce").fillna(1)
    if "floor" in col.lower():
        values = values * 3.2
    return values

def _bbox_gap(a, b):
    dx = max(float(a["minx"]) - float(b["maxx"]), float(b["minx"]) - float(a["maxx"]), 0)
    dy = max(float(a["miny"]) - float(b["maxy"]), float(b["miny"]) - float(a["maxy"]), 0)
    return (dx ** 2 + dy ** 2) ** 0.5

def _direction_from_to(source, target):
    dx = float(target["centroid_x"]) - float(source["centroid_x"])
    dy = float(target["centroid_y"]) - float(source["centroid_y"])
    if abs(dx) > abs(dy):
        return "east" if dx > 0 else "west"
    return "north" if dy > 0 else "south"

def chart_massing_shading(cea_data, selected_buildings, output_mode):
    """
    Massing & shading strategy — site context chart using project and surroundings geometry.
    Shows building positions and heights, with obstruction links when a building is selected.
    """
    zone = cea_data["files"].get("zone_geometry.csv")
    surroundings = cea_data["files"].get("surroundings_geometry.csv")
    required = ["centroid_x", "centroid_y", "minx", "miny", "maxx", "maxy"]
    if zone is None or surroundings is None:
        return chart_solar_irradiation(cea_data, selected_buildings, output_mode)
    if any(c not in zone.columns for c in required) or any(c not in surroundings.columns for c in required):
        return chart_solar_irradiation(cea_data, selected_buildings, output_mode)

    zone = zone.copy()
    surroundings = surroundings.copy()
    name_col = _find_col(zone, "name", "Name", "building")
    s_name_col = _find_col(surroundings, "name", "Name", "building")
    h_col = _height_col(zone)
    s_h_col = _height_col(surroundings)

    zone["height_m"] = _height_series(zone, h_col)
    surroundings["height_m"] = _height_series(surroundings, s_h_col)
    zone["type"] = "Project building"
    surroundings["type"] = "Surrounding building"
    zone["label"] = zone[name_col].astype(str) if name_col else "Project"
    surroundings["label"] = surroundings[s_name_col].astype(str) if s_name_col else "Surrounding"

    if selected_buildings and name_col:
        zone["focus"] = zone[name_col].isin(selected_buildings)
    else:
        zone["focus"] = True
    surroundings["focus"] = False

    focus_zone = zone[zone["focus"]]
    if focus_zone.empty:
        focus_zone = zone

    buffer_m = 180 if selected_buildings else 120
    minx = float(focus_zone["minx"].min()) - buffer_m
    maxx = float(focus_zone["maxx"].max()) + buffer_m
    miny = float(focus_zone["miny"].min()) - buffer_m
    maxy = float(focus_zone["maxy"].max()) + buffer_m
    surroundings = surroundings[
        (surroundings["centroid_x"] >= minx) & (surroundings["centroid_x"] <= maxx) &
        (surroundings["centroid_y"] >= miny) & (surroundings["centroid_y"] <= maxy)
    ].copy()

    links = []
    if not focus_zone.empty:
        for _, building in focus_zone.iterrows():
            bheight = float(building["height_m"]) if building["height_m"] == building["height_m"] else 0
            external_candidates = []
            project_candidates = []
            neighbour_sources = [
                ("External surrounding", surroundings),
                ("Project-to-project", zone[zone["label"] != building["label"]]),
            ]
            for source_type, source_df in neighbour_sources:
                for _, neighbour in source_df.iterrows():
                    if str(neighbour["label"]) == str(building["label"]):
                        continue
                    nheight = float(neighbour["height_m"]) if neighbour["height_m"] == neighbour["height_m"] else 0
                    distance = _bbox_gap(building, neighbour)
                    critical_distance = max(nheight * 2, 1)
                    if distance <= critical_distance or nheight > bheight:
                        candidate = {
                            "target": str(building["label"]),
                            "source": str(neighbour["label"]),
                            "source_type": source_type,
                            "x1": float(building["centroid_x"]),
                            "y1": float(building["centroid_y"]),
                            "x2": float(neighbour["centroid_x"]),
                            "y2": float(neighbour["centroid_y"]),
                            "distance_m": distance,
                            "height_m": nheight,
                            "direction": _direction_from_to(building, neighbour),
                        }
                        if source_type == "Project-to-project":
                            project_candidates.append(candidate)
                        else:
                            external_candidates.append(candidate)
            links.extend(sorted(project_candidates, key=lambda item: item["distance_m"])[:5])
            links.extend(sorted(external_candidates, key=lambda item: item["distance_m"])[:5])

    linked_names = {item["source"] for item in links}
    if linked_names:
        surroundings = surroundings[
            surroundings["label"].isin(linked_names) |
            (surroundings["height_m"] >= surroundings["height_m"].quantile(0.75))
        ].copy()
    elif len(surroundings) > 45:
        surroundings["_dist_to_focus"] = surroundings.apply(
            lambda row: min(_bbox_gap(row, building) for _, building in focus_zone.iterrows()),
            axis=1
        )
        surroundings = surroundings.nsmallest(45, "_dist_to_focus").copy()

    plot_df = pd.concat([
        zone[["centroid_x", "centroid_y", "height_m", "type", "label", "focus"]],
        surroundings[["centroid_x", "centroid_y", "height_m", "type", "label", "focus"]],
    ], ignore_index=True)
    origin_x = float(plot_df["centroid_x"].min())
    origin_y = float(plot_df["centroid_y"].min())
    plot_df["x_local"] = plot_df["centroid_x"] - origin_x
    plot_df["y_local"] = plot_df["centroid_y"] - origin_y

    base = alt.Chart(plot_df).mark_circle(opacity=0.82, stroke="#ffffff", strokeWidth=0.8).encode(
        x=alt.X("x_local:Q", title="Local site x (m)", scale=alt.Scale(zero=False)),
        y=alt.Y("y_local:Q", title="Local site y (m)", scale=alt.Scale(zero=False)),
        size=alt.Size("height_m:Q", title="Height (m)", scale=alt.Scale(range=[60, 900])),
        color=alt.Color("type:N", scale=alt.Scale(
            domain=["Project building", "Surrounding building"],
            range=[C_PV, C_NEUTRAL]
        ), legend=alt.Legend(title="Massing")),
        strokeDash=alt.condition("datum.focus", alt.value([1, 0]), alt.value([2, 2])),
        tooltip=[
            alt.Tooltip("label:N", title="Building"),
            alt.Tooltip("type:N", title="Type"),
            alt.Tooltip("height_m:Q", title="Height (m)", format=".1f"),
        ]
    )

    labels = alt.Chart(plot_df[plot_df["type"] == "Project building"]).mark_text(
        dy=-12, fontSize=10, color=C_DEMAND
    ).encode(
        x="x_local:Q",
        y="y_local:Q",
        text="label:N"
    )

    chart = base + labels
    if links:
        link_df = pd.DataFrame(links)
        link_df["x1_local"] = link_df["x1"] - origin_x
        link_df["y1_local"] = link_df["y1"] - origin_y
        link_df["x2_local"] = link_df["x2"] - origin_x
        link_df["y2_local"] = link_df["y2"] - origin_y
        segments = pd.concat([
            link_df.assign(x=link_df["x1_local"], y=link_df["y1_local"], order=0),
            link_df.assign(x=link_df["x2_local"], y=link_df["y2_local"], order=1),
        ])
        link_chart = alt.Chart(segments).mark_line(
            opacity=0.6, strokeDash=[4, 3]
        ).encode(
            x="x:Q",
            y="y:Q",
            detail="source:N",
            order="order:Q",
            color=alt.Color("source_type:N", scale=alt.Scale(
                domain=["External surrounding", "Project-to-project"],
                range=[C_CARBON, C_DEMAND]
            ), legend=alt.Legend(title="Obstruction link")),
            tooltip=[
                alt.Tooltip("source:N", title="Potential obstruction"),
                alt.Tooltip("source_type:N", title="Source type"),
                alt.Tooltip("target:N", title="Target"),
                alt.Tooltip("direction:N", title="Direction"),
                alt.Tooltip("distance_m:Q", title="Gap (m)", format=".1f"),
                alt.Tooltip("height_m:Q", title="Obstruction height (m)", format=".1f"),
            ]
        )
        chart = link_chart + chart

    return chart.properties(
        title="Massing context: surrounding height and obstruction proximity",
        height=360
    ).configure_view(strokeWidth=0)

def chart_solar_irradiation(cea_data, selected_buildings, output_mode):
    """
    Solar irradiation skills.
    Uses per-surface columns: irradiation_roof[kWh], irradiation_wall_south[kWh], etc.
    Key takeaway     → stacked bar by surface orientation
    Explain numbers  → stacked bar + seasonal breakdown
    Design impl.     → surface comparison horizontal bar
    """
    df_b = cea_data["files"].get("solar_irradiation_annually_buildings.csv")
    if df_b is None:
        pv_fname = next((k for k in cea_data["files"]
                         if k.startswith("PV_PV") and "_total.csv" in k
                         and "buildings" not in k), None)
        if pv_fname:
            rows = _pv_surface_generation_rows(cea_data, pv_fname, selected_buildings)
            if rows:
                df_pv_surface = pd.DataFrame(rows)
                surface_order = ["Roof", "South facade", "East facade", "West facade", "North facade"]
                color_range = [C_PV, C_SURPLUS, "#e8b86d", "#a8d5b5", C_NEUTRAL]
                return alt.Chart(df_pv_surface).mark_bar(
                    cornerRadiusTopLeft=3, cornerRadiusTopRight=3
                ).encode(
                    x=alt.X("Surface:N", sort=surface_order, title="", axis=alt.Axis(labelAngle=-20)),
                    y=alt.Y("MWh:Q", title="PV yield (MWh/year)"),
                    color=alt.Color("Surface:N", scale=alt.Scale(domain=surface_order, range=color_range), legend=None),
                    tooltip=[
                        alt.Tooltip("Surface:N"),
                        alt.Tooltip("MWh:Q", title="MWh/year", format=",.1f"),
                    ],
                ).properties(
                    title="PV yield by active roof/facade surface",
                    height=280
                )
        return None

    name_col = _find_col(df_b, "name", "Name", "building")
    if name_col is None:
        return None

    df_b = df_b.copy()
    if selected_buildings:
        df_b = df_b[df_b[name_col].isin(selected_buildings)]
    if df_b.empty:
        return None

    # Find surface-specific columns (exclude windows)
    surface_map = {
        "Roof":        next((c for c in df_b.columns if "roof" in c.lower() and "window" not in c.lower()), None),
        "South wall":  next((c for c in df_b.columns if "south" in c.lower() and "window" not in c.lower()), None),
        "East wall":   next((c for c in df_b.columns if "east" in c.lower() and "window" not in c.lower()), None),
        "West wall":   next((c for c in df_b.columns if "west" in c.lower() and "window" not in c.lower()), None),
        "North wall":  next((c for c in df_b.columns if "north" in c.lower() and "window" not in c.lower()), None),
    }
    found = {k: v for k, v in surface_map.items() if v is not None and _num(df_b[v]).sum() > 0}

    if not found:
        # Fallback: use first kWh column found
        rad_col = _find_col(df_b, "kWh", "radiation", "irr")
        if rad_col is None:
            return None
        df_b = df_b.sort_values(rad_col, ascending=False).head(10)
        return alt.Chart(df_b).mark_bar(color=C_PV, cornerRadiusTopLeft=3,
                                         cornerRadiusTopRight=3).encode(
            x=alt.X(f"{rad_col}:Q", title="Annual irradiation (kWh/yr)"),
            y=alt.Y(f"{name_col}:N", sort="-x", title=""),
            tooltip=[name_col, alt.Tooltip(f"{rad_col}:Q", format=",.0f")]
        ).properties(title="Annual irradiation by building", height=max(100, len(df_b) * 25))

    # Build long-format dataframe for surface breakdown
    rows = []
    for _, row in df_b.iterrows():
        for surface, col in found.items():
            rows.append({
                "building": row[name_col],
                "surface": surface,
                "kWh": float(pd.to_numeric(pd.Series([row[col]]), errors="coerce").fillna(0).iloc[0])
            })
    import pandas as pd_inner
    df_long = pd_inner.DataFrame(rows)

    surface_order = [s for s in ["Roof", "South wall", "East wall", "West wall", "North wall"] if s in found]
    color_range = [C_PV, C_SURPLUS, "#e8b86d", "#a8d5b5", C_NEUTRAL][:len(surface_order)]

    if output_mode == "Key takeaway":
        # Aggregate across buildings, show total by surface
        df_agg = df_long.groupby("surface")["kWh"].sum().reset_index()
        df_agg = df_agg[df_agg["kWh"] > 0].sort_values("kWh", ascending=False)
        chart = alt.Chart(df_agg).mark_bar(cornerRadiusTopLeft=3,
                                            cornerRadiusTopRight=3).encode(
            x=alt.X("surface:N", sort="-y", title="Surface", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("kWh:Q", title="Total annual irradiation (kWh/yr)"),
            color=alt.Color("surface:N", scale=alt.Scale(
                domain=surface_order, range=color_range), legend=None),
            tooltip=["surface", alt.Tooltip("kWh:Q", format=",.0f", title="kWh/yr")]
        ).properties(title="Annual irradiation by surface orientation", height=200)
        return chart

    # Explain numbers / Design implication
    n_buildings = df_b[name_col].nunique()

    if n_buildings == 1:
        # Single building — show each surface as its own bar
        df_agg = df_long.groupby("surface")["kWh"].sum().reset_index()
        df_agg = df_agg[df_agg["kWh"] > 0]
        chart = alt.Chart(df_agg).mark_bar(cornerRadiusTopLeft=3,
                                            cornerRadiusTopRight=3).encode(
            x=alt.X("surface:N", sort=surface_order, title="Surface",
                    axis=alt.Axis(labelAngle=0)),
            y=alt.Y("kWh:Q", title="Annual irradiation (kWh/yr)"),
            color=alt.Color("surface:N", scale=alt.Scale(
                domain=surface_order, range=color_range), legend=None),
            tooltip=["surface", alt.Tooltip("kWh:Q", format=",.0f", title="kWh/yr")]
        ).properties(title="Annual irradiation by surface orientation", height=250)
    else:
        # Multiple buildings — stacked bars per building
        chart = alt.Chart(df_long).mark_bar().encode(
            x=alt.X("building:N", title="", axis=alt.Axis(labelAngle=-30)),
            y=alt.Y("kWh:Q", title="Annual irradiation (kWh/yr)"),
            color=alt.Color("surface:N", scale=alt.Scale(
                domain=surface_order, range=color_range),
                legend=alt.Legend(title="Surface")),
            order=alt.Order("surface:N"),
            tooltip=["building", "surface", alt.Tooltip("kWh:Q", format=",.0f", title="kWh/yr")]
        ).properties(title="Annual irradiation by building and surface", height=250)
    return chart


def chart_energy_generation(cea_data, selected_buildings, output_mode):
    """
    PV energy generation.
    Key takeaway     → monthly PV bar (single series)
    Explain numbers  → monthly PV bar + daily profile line
    Design impl.     → surface contribution donut + monthly bar
    """
    pv_fname = next((k for k in cea_data["files"]
                     if k.startswith("PV_PV") and "_total.csv" in k
                     and "buildings" not in k), None)
    if pv_fname is None:
        return None

    df_pv = cea_data["files"][pv_fname].copy()
    gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen")
    if gen_col is None:
        return None

    pv_scale = 1.0
    if selected_buildings:
        bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
        df_b_scale = cea_data["files"].get(bldg_fname)
        name_col_scale = _find_col(df_b_scale, "name", "Name", "building") if df_b_scale is not None else None
        gen_b_col_scale = _find_col(df_b_scale, "E_PV_gen", "E_PV", "gen") if df_b_scale is not None else None
        if df_b_scale is not None and name_col_scale and gen_b_col_scale:
            selected_df = df_b_scale[df_b_scale[name_col_scale].isin(selected_buildings)]
            selected_annual = pd.to_numeric(selected_df[gen_b_col_scale], errors="coerce").fillna(0).sum()
            district_annual = pd.to_numeric(df_pv[gen_col], errors="coerce").fillna(0).sum()
            if district_annual > 0 and selected_annual > 0:
                pv_scale = float(selected_annual / district_annual)

    monthly = _monthly_from_hourly(df_pv, gen_col)
    if monthly is None:
        return None
    monthly = monthly * pv_scale

    surface_pie = _pv_surface_pie_chart(cea_data, pv_fname, selected_buildings)

    df_monthly = pd.DataFrame({
        "Month": MONTHS, "Generation (MWh)": monthly.values
    })
    df_monthly["month_num"] = range(1, 13)

    monthly_bar = alt.Chart(df_monthly).mark_bar(
        color=C_PV, cornerRadiusTopLeft=3, cornerRadiusTopRight=3
    ).encode(
        x=alt.X("Month:N", sort=MONTHS, title=""),
        y=alt.Y("Generation (MWh):Q", title="MWh"),
        tooltip=["Month", alt.Tooltip("Generation (MWh):Q", format=".1f")]
    ).properties(title="Monthly PV generation", height=240, width=720)

    if output_mode == "Key takeaway":
        return surface_pie if surface_pie is not None else monthly_bar

    if output_mode == "Explain the numbers":
        # Add daily profile
        date_col = _find_col(df_pv, "date", "Date", "time")
        if date_col:
            try:
                df_pv["_dt"] = pd.to_datetime(df_pv[date_col], utc=True, errors="coerce")
                df_pv["hour"] = df_pv["_dt"].dt.hour
                hourly_avg = df_pv.groupby("hour")[gen_col].mean() * pv_scale / 1000
                df_hourly = pd.DataFrame({
                    "Hour": hourly_avg.index,
                    "Avg generation (MWh)": hourly_avg.values
                })
                profile = alt.Chart(df_hourly).mark_area(
                    color=C_PV, opacity=0.4, line={"color": C_PV, "strokeWidth": 2}
                ).encode(
                    x=alt.X("Hour:Q", title="Hour of day",
                            scale=alt.Scale(domain=[0, 23])),
                    y=alt.Y("Avg generation (MWh):Q", title="MWh (avg)"),
                    tooltip=["Hour", alt.Tooltip("Avg generation (MWh):Q", format=".2f")]
                ).properties(title="Average daily generation profile", height=240, width=720)
                if surface_pie is not None:
                    return alt.vconcat(surface_pie, monthly_bar, profile, spacing=24)
                return alt.vconcat(monthly_bar, profile, spacing=24)
            except Exception:
                pass
        return alt.vconcat(surface_pie, monthly_bar, spacing=24) if surface_pie is not None else monthly_bar

    if output_mode == "Design implication":
        # Surface contribution from buildings file: roof/facade share of total PV generation
        bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
        df_b = cea_data["files"].get(bldg_fname)
        name_col = _find_col(df_b, "name", "Name") if df_b is not None else None
        gen_b_col = _find_col(df_b, "E_PV_gen", "E_PV") if df_b is not None else None

        if df_b is not None:
            if selected_buildings:
                if name_col:
                    df_b = df_b[df_b[name_col].isin(selected_buildings)]
            df_b = df_b.copy()

            surface_cols = [
                ("Roof", "PV_roofs_top_E_kWh"),
                ("South facade", "PV_walls_south_E_kWh"),
                ("East facade", "PV_walls_east_E_kWh"),
                ("West facade", "PV_walls_west_E_kWh"),
                ("North facade", "PV_walls_north_E_kWh"),
            ]
            rows = []
            for surface, col in surface_cols:
                if col in df_b.columns:
                    kwh = pd.to_numeric(df_b[col], errors="coerce").fillna(0).sum()
                    if kwh > 0:
                        rows.append({"Surface": surface, "Generation (MWh)": kwh / 1000})

            if rows:
                df_surface = pd.DataFrame(rows)
                total = df_surface["Generation (MWh)"].sum()
                df_surface["Share"] = df_surface["Generation (MWh)"] / total
                surface_order = [r[0] for r in surface_cols]
                color_range = [C_PV, C_SURPLUS, "#e8b86d", "#a8d5b5", C_NEUTRAL]

                if surface_pie is not None:
                    return surface_pie & monthly_bar

            if name_col and gen_b_col:
                df_b["annual_MWh"] = df_b[gen_b_col] / 1000
                donut = alt.Chart(df_b.nlargest(8, gen_b_col)).mark_arc(
                    innerRadius=50
                ).encode(
                    theta=alt.Theta("annual_MWh:Q"),
                    color=alt.Color(f"{name_col}:N",
                                    scale=alt.Scale(scheme="goldorange")),
                    tooltip=[name_col, alt.Tooltip("annual_MWh:Q", format=".1f",
                                                   title="MWh/yr")]
                ).properties(title="Generation share by building", height=220)
                return monthly_bar | donut

        return monthly_bar


def chart_panel_type_tradeoff(cea_data, selected_buildings, output_mode):
    """
    Panel type trade-off.
    Shows all simulated PV panel options together so PV1/PV2/PV3/PV4 can be compared directly.
    """
    pv_fnames = sorted(
        k for k in cea_data["files"]
        if k.startswith("PV_PV") and k.endswith("_total.csv") and "buildings" not in k
    )
    if not pv_fnames:
        return None

    panel_colors = ["#c8a96e", "#7ec8a0", "#e07b5a", "#6b8fd6", "#a0a0a0"]
    monthly_rows = []
    daily_rows = []
    summary_rows = []

    for pv_fname in pv_fnames:
        df_pv = cea_data["files"][pv_fname].copy()
        gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen")
        if gen_col is None:
            continue

        panel_type = pv_fname.replace("PV_", "").replace("_total.csv", "")
        monthly = _monthly_from_hourly(df_pv, gen_col)
        if monthly is None:
            continue

        district_annual = float(pd.to_numeric(df_pv[gen_col], errors="coerce").fillna(0).sum())
        annual_kwh = district_annual
        area_m2 = None
        pv_scale = 1.0

        bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
        df_b = cea_data["files"].get(bldg_fname)
        if df_b is not None:
            name_col = _find_col(df_b, "name", "Name", "building")
            gen_b_col = _find_col(df_b, "E_PV_gen", "E_PV", "gen")
            df_use = df_b.copy()
            if selected_buildings and name_col:
                df_use = df_use[df_use[name_col].isin(selected_buildings)]
            if gen_b_col and not df_use.empty:
                annual_kwh = float(pd.to_numeric(df_use[gen_b_col], errors="coerce").fillna(0).sum())
                if district_annual > 0:
                    pv_scale = annual_kwh / district_annual
                    monthly = monthly * pv_scale

            area_cols = [
                c for c in df_use.columns
                if c.endswith("_m2") and ("PV_roofs" in c or "PV_walls" in c or "area_PV" in c)
            ]
            if area_cols and not df_use.empty:
                area_m2 = float(sum(pd.to_numeric(df_use[c], errors="coerce").fillna(0).sum() for c in area_cols))

        for month_num, mwh in monthly.items():
            monthly_rows.append({
                "Panel type": panel_type,
                "Month": MONTHS[int(month_num) - 1],
                "month_num": int(month_num),
                "Generation (MWh)": float(mwh),
            })

        date_col = _find_col(df_pv, "date", "Date", "time")
        if date_col:
            work = df_pv.copy()
            work["_dt"] = pd.to_datetime(work[date_col], utc=True, errors="coerce")
            work["_hour"] = work["_dt"].dt.hour
            hourly_avg = (
                pd.to_numeric(work[gen_col], errors="coerce").fillna(0)
                .groupby(work["_hour"]).mean()
                * pv_scale / 1000
            )
            hourly_avg = hourly_avg.reindex(range(24), fill_value=0)
            for hour, mwh in hourly_avg.items():
                daily_rows.append({
                    "Panel type": panel_type,
                    "Hour": int(hour),
                    "Average generation (MWh)": float(mwh),
                })

        annual_mwh = annual_kwh / 1000
        summary_rows.append({
            "Panel type": panel_type,
            "Annual generation (MWh)": annual_mwh,
            "Installed area (m2)": area_m2,
            "Yield (kWh/m2/year)": annual_kwh / area_m2 if area_m2 and area_m2 > 0 else None,
        })

    if not monthly_rows or not daily_rows:
        return None

    df_monthly = pd.DataFrame(monthly_rows)
    df_daily = pd.DataFrame(daily_rows)
    panel_order = sorted(df_monthly["Panel type"].unique())
    color_range = panel_colors[:len(panel_order)]

    monthly_line = alt.Chart(df_monthly).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("Month:N", sort=MONTHS, title=""),
        y=alt.Y("Generation (MWh):Q", title="MWh"),
        color=alt.Color(
            "Panel type:N",
            scale=alt.Scale(domain=panel_order, range=color_range),
            legend=alt.Legend(title="Panel type")
        ),
        tooltip=[
            "Panel type",
            "Month",
            alt.Tooltip("Generation (MWh):Q", format=",.1f", title="MWh"),
        ],
    ).properties(title="Monthly generation by panel type", height=220)

    daily_line = alt.Chart(df_daily).mark_line(strokeWidth=2).encode(
        x=alt.X("Hour:Q", title="Hour of day", scale=alt.Scale(domain=[0, 23]),
                axis=alt.Axis(tickMinStep=1)),
        y=alt.Y("Average generation (MWh):Q", title="MWh (avg)"),
        color=alt.Color(
            "Panel type:N",
            scale=alt.Scale(domain=panel_order, range=color_range),
            legend=alt.Legend(title="Panel type")
        ),
        tooltip=[
            "Panel type",
            "Hour",
            alt.Tooltip("Average generation (MWh):Q", format=",.3f", title="Avg MWh"),
        ],
    ).properties(title="Average daily generation profile by panel type", height=220)

    return monthly_line | daily_line


def chart_self_sufficiency(cea_data, selected_buildings, output_mode):
    """
    PV vs demand — self-sufficiency.
    Key takeaway     → monthly stacked bar PV / demand
    Explain numbers  → monthly grouped bar + surplus/deficit area
    Design impl.     → monthly surplus/deficit area chart
    """
    pv_fname = next((k for k in cea_data["files"]
                     if k.startswith("PV_PV") and "_total.csv" in k
                     and "buildings" not in k), None)
    if pv_fname is None:
        return None

    df_pv = cea_data["files"][pv_fname].copy()
    gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen")
    date_col = _find_col(df_pv, "date", "Date", "time")
    if gen_col is None or date_col is None:
        return None

    pv_scale = 1.0
    if selected_buildings:
        bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
        df_b_scale = cea_data["files"].get(bldg_fname)
        name_col_scale = _find_col(df_b_scale, "name", "Name", "building") if df_b_scale is not None else None
        gen_b_col_scale = _find_col(df_b_scale, "E_PV_gen", "E_PV", "gen") if df_b_scale is not None else None
        if df_b_scale is not None and name_col_scale and gen_b_col_scale:
            selected_df = df_b_scale[df_b_scale[name_col_scale].isin(selected_buildings)]
            selected_annual = pd.to_numeric(selected_df[gen_b_col_scale], errors="coerce").fillna(0).sum()
            district_annual = pd.to_numeric(df_pv[gen_col], errors="coerce").fillna(0).sum()
            if district_annual > 0 and selected_annual > 0:
                pv_scale = float(selected_annual / district_annual)

    # Aggregate demand from building files
    demand_files = [
        v for k, v in cea_data["files"].items()
        if k.startswith("B") and k.endswith(".csv") and len(k) <= 10
        and (not selected_buildings or k.replace(".csv", "") in selected_buildings)
    ]
    total_demand_df = cea_data["files"].get("Total_demand.csv")

    try:
        df_pv["_dt"] = pd.to_datetime(df_pv[date_col], utc=True, errors="coerce")
        df_pv["month"] = df_pv["_dt"].dt.month
        monthly_pv = df_pv.groupby("month")[gen_col].sum() * pv_scale / 1000

        if demand_files:
            demand_col = _find_col(demand_files[0], "E_sys", "GRID", "E_tot")
            if demand_col:
                demand_series = None
                for d in demand_files:
                    d_col = _find_col(d, "E_sys", "GRID", "E_tot")
                    if d_col:
                        values = pd.to_numeric(d[d_col], errors="coerce").fillna(0).reset_index(drop=True)
                        demand_series = values if demand_series is None else demand_series.add(values, fill_value=0)
                if demand_series is None:
                    return None
                df_demand = df_pv.copy()
                n = min(len(df_demand), len(demand_series))
                df_demand = df_demand.iloc[:n].copy()
                df_demand["_demand"] = demand_series.iloc[:n].values
                monthly_demand = df_demand.groupby("month")["_demand"].sum() / 1000
            else:
                return None
        elif total_demand_df is not None:
            d_col = _find_col(total_demand_df, "E_sys", "GRID", "E_tot")
            if d_col is None:
                return None
            monthly_demand = pd.Series(
                [total_demand_df[d_col].sum() / 12] * 12, index=range(1, 13)
            )
        else:
            return None

        df_chart = pd.DataFrame({
            "Month": MONTHS,
            "PV Generation (MWh)": monthly_pv.reindex(range(1, 13), fill_value=0).values,
            "Demand (MWh)": monthly_demand.reindex(range(1, 13), fill_value=0).values,
        })
        df_chart["Surplus (MWh)"] = (df_chart["PV Generation (MWh)"]
                                     - df_chart["Demand (MWh)"]).clip(lower=0)
        df_chart["Deficit (MWh)"] = (df_chart["Demand (MWh)"]
                                     - df_chart["PV Generation (MWh)"]).clip(lower=0)

        if output_mode == "Key takeaway":
            df_long = df_chart.melt("Month", ["PV Generation (MWh)", "Demand (MWh)"],
                                    var_name="Series", value_name="MWh")
            chart = alt.Chart(df_long).mark_bar(cornerRadiusTopLeft=2,
                                                 cornerRadiusTopRight=2).encode(
                x=alt.X("Month:N", sort=MONTHS, title=""),
                y=alt.Y("MWh:Q", title="MWh"),
                color=alt.Color("Series:N", scale=alt.Scale(
                    domain=["PV Generation (MWh)", "Demand (MWh)"],
                    range=[C_PV, C_DEMAND])),
                xOffset="Series:N",
                tooltip=["Month", "Series", alt.Tooltip("MWh:Q", format=".1f")]
            ).properties(title="Monthly PV generation vs demand", height=220)
            return chart

        if output_mode in ("Explain the numbers", "Design implication"):
            df_sd = df_chart.melt("Month", ["Surplus (MWh)", "Deficit (MWh)"],
                                  var_name="Type", value_name="MWh")
            surplus_chart = alt.Chart(df_sd).mark_bar(cornerRadiusTopLeft=2,
                                                       cornerRadiusTopRight=2).encode(
                x=alt.X("Month:N", sort=MONTHS, title=""),
                y=alt.Y("MWh:Q", title="MWh"),
                color=alt.Color("Type:N", scale=alt.Scale(
                    domain=["Surplus (MWh)", "Deficit (MWh)"],
                    range=[C_SURPLUS_YELLOW, C_DEFICIT_GREY])),
                xOffset="Type:N",
                tooltip=["Month", "Type", alt.Tooltip("MWh:Q", format=".1f")]
            ).properties(title="Monthly surplus & deficit", height=220)

            df_long = df_chart.melt("Month", ["PV Generation (MWh)", "Demand (MWh)"],
                                    var_name="Series", value_name="MWh")
            grouped = alt.Chart(df_long).mark_bar(cornerRadiusTopLeft=2,
                                                   cornerRadiusTopRight=2).encode(
                x=alt.X("Month:N", sort=MONTHS, title=""),
                y=alt.Y("MWh:Q", title="MWh"),
                color=alt.Color("Series:N", scale=alt.Scale(
                    domain=["PV Generation (MWh)", "Demand (MWh)"],
                    range=[C_PV, C_DEMAND])),
                xOffset="Series:N",
                tooltip=["Month", "Series", alt.Tooltip("MWh:Q", format=".1f")]
            ).properties(title="Monthly PV vs demand", height=220)

            return (grouped | surplus_chart).resolve_scale(color="independent")

    except Exception:
        return None


def _grid_carbon_factor_kgco2_kwh(cea_data):
    grid_df = cea_data["files"].get("GRID.csv")
    em_col = _find_col(grid_df, "GHG_kgCO2MJ", "CO2", "co2", "emission", "GHG") if grid_df is not None else None
    if em_col and grid_df is not None:
        try:
            value = float(pd.to_numeric(grid_df[em_col], errors="coerce").dropna().iloc[0])
            return value * 3.6 if "MJ" in em_col else value
        except Exception:
            pass
    return 0.4


def _demand_series_for_scope(cea_data, selected_buildings):
    demand_files = [
        v for k, v in cea_data["files"].items()
        if k.startswith("B") and k.endswith(".csv") and len(k) <= 10
        and (not selected_buildings or k.replace(".csv", "") in selected_buildings)
    ]
    demand_series = None
    for df in demand_files:
        d_col = _find_col(df, "E_sys", "GRID", "E_tot")
        if d_col:
            values = pd.to_numeric(df[d_col], errors="coerce").fillna(0).reset_index(drop=True)
            demand_series = values if demand_series is None else demand_series.add(values, fill_value=0)
    return demand_series


def _pv_scope_from_first_total(cea_data, selected_buildings):
    pv_fname = next((k for k in cea_data["files"]
                     if k.startswith("PV_PV") and "_total.csv" in k
                     and "buildings" not in k), None)
    if pv_fname is None:
        return None

    df_pv = cea_data["files"][pv_fname].copy()
    gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen")
    if gen_col is None:
        return None

    district_annual = float(pd.to_numeric(df_pv[gen_col], errors="coerce").fillna(0).sum())
    annual_kwh = district_annual
    area_m2 = None
    roof_area_m2 = 0.0
    facade_area_m2 = 0.0
    scale = 1.0

    bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
    df_b = cea_data["files"].get(bldg_fname)
    if df_b is not None:
        name_col = _find_col(df_b, "name", "Name", "building")
        gen_b_col = _find_col(df_b, "E_PV_gen", "E_PV", "gen")
        df_use = df_b.copy()
        if selected_buildings and name_col:
            df_use = df_use[df_use[name_col].isin(selected_buildings)]
        if gen_b_col and not df_use.empty:
            annual_kwh = float(pd.to_numeric(df_use[gen_b_col], errors="coerce").fillna(0).sum())
            if district_annual > 0:
                scale = annual_kwh / district_annual

        roof_col = _find_col(df_use, "PV_roofs_top_m2")
        if roof_col:
            roof_area_m2 = float(pd.to_numeric(df_use[roof_col], errors="coerce").fillna(0).sum())
        for direction in ["south", "east", "west", "north"]:
            col = _find_col(df_use, f"PV_walls_{direction}_m2")
            if col:
                facade_area_m2 += float(pd.to_numeric(df_use[col], errors="coerce").fillna(0).sum())
        area_m2 = roof_area_m2 + facade_area_m2
        if area_m2 <= 0:
            area_cols = [
                c for c in df_use.columns
                if c.endswith("_m2") and ("PV_roofs" in c or "PV_walls" in c or "area_PV" in c)
            ]
            if area_cols:
                area_m2 = float(sum(pd.to_numeric(df_use[c], errors="coerce").fillna(0).sum() for c in area_cols))

    return {
        "pv_fname": pv_fname,
        "df_pv": df_pv,
        "gen_col": gen_col,
        "annual_kwh": annual_kwh,
        "district_annual_kwh": district_annual,
        "scale": scale,
        "area_m2": area_m2,
        "roof_area_m2": roof_area_m2,
        "facade_area_m2": facade_area_m2,
    }


def chart_carbon_footprint(cea_data, selected_buildings, output_mode):
    """
    Lifecycle carbon decomposition: embodied carbon, replaced material credit, and operational savings.
    """
    scope = _pv_scope_from_first_total(cea_data, selected_buildings)
    if scope is None:
        return None

    annual_gen_kwh = scope["annual_kwh"]
    total_area = scope["area_m2"]
    if annual_gen_kwh <= 0 or not total_area or total_area <= 0:
        return None

    embodied_tco2 = _panel_embodied_carbon_kg_m2(cea_data) * total_area / 1000
    # Conservative material replacement credit when no project-specific cladding EPD is supplied.
    displaced_material_tco2 = 35.0 * total_area / 1000
    annual_operational_saving_tco2 = annual_gen_kwh * _grid_carbon_factor_kgco2_kwh(cea_data) / 1000
    lifetime_years = 25
    lifetime_saving_tco2 = annual_operational_saving_tco2 * lifetime_years

    net_tco2 = embodied_tco2 - displaced_material_tco2 - lifetime_saving_tco2
    rows = [
        {
            "Item": "Carbon added by making BIPV",
            "tCO2e": embodied_tco2,
            "Meaning": "Adds carbon before operation starts",
            "Type": "Adds carbon",
        },
        {
            "Item": "Carbon avoided by replacing cladding",
            "tCO2e": -displaced_material_tco2,
            "Meaning": "Credit because BIPV replaces another facade/roof material",
            "Type": "Avoids carbon",
        },
        {
            "Item": "Carbon avoided from electricity over 25 years",
            "tCO2e": -lifetime_saving_tco2,
            "Meaning": "Credit from PV electricity replacing grid electricity",
            "Type": "Avoids carbon",
        },
        {
            "Item": "Net carbon balance after 25 years",
            "tCO2e": net_tco2,
            "Meaning": "Final balance: negative is beneficial",
            "Type": "Net result",
        },
    ]
    df_chart = pd.DataFrame(rows)

    chart = alt.Chart(df_chart).mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3).encode(
        y=alt.Y("Item:N", title="", sort=[row["Item"] for row in rows]),
        x=alt.X("tCO2e:Q", title="tCO2e over 25 years (negative = avoided carbon)"),
        color=alt.Color(
            "Type:N",
            scale=alt.Scale(
                domain=["Adds carbon", "Avoids carbon", "Net result"],
                range=[C_CARBON, C_SURPLUS, C_DEMAND]
            ),
            legend=alt.Legend(title="")
        ),
        tooltip=[
            alt.Tooltip("Item:N"),
            alt.Tooltip("Meaning:N"),
            alt.Tooltip("tCO2e:Q", title="tCO2e", format=",.1f"),
        ],
    ).properties(
        title="Carbon footprint balance: what BIPV adds and what it avoids",
        height=260,
        width=720
    )
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=C_NEUTRAL, strokeDash=[4, 4]).encode(x="x:Q")
    return chart + zero


def chart_carbon(cea_data, selected_buildings, output_mode):
    """
    Carbon payback period: break-even timeline.
    """
    scope = _pv_scope_from_first_total(cea_data, selected_buildings)
    if scope is None:
        return None

    annual_gen_kwh = scope["annual_kwh"]
    if annual_gen_kwh <= 0:
        return None

    em_grid = _grid_carbon_factor_kgco2_kwh(cea_data)

    em_bipv = _panel_embodied_carbon_kg_m2(cea_data)

    total_area = scope["area_m2"]
    if not total_area or total_area <= 0:
        return None
    embodied_total = em_bipv * total_area  # kgCO2
    annual_avoided = annual_gen_kwh * em_grid  # kgCO2/yr

    if annual_avoided <= 0:
        return None

    payback_yr = embodied_total / annual_avoided
    years = list(range(0, 26))
    embodied_tco2 = embodied_total / 1000
    cumulative_avoided = [annual_avoided * y / 1000 for y in years]
    carbon_debt = [max(embodied_tco2 - value, 0) for value in cumulative_avoided]

    df_payback = pd.DataFrame({"Year": years, "Cumulative operational savings": cumulative_avoided, "Carbon debt remaining": carbon_debt})
    df_long = df_payback.melt("Year", var_name="Series", value_name="tCO2")

    chart = alt.Chart(df_long).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("Year:Q", title="Years of operation"),
        y=alt.Y("tCO2:Q", title="tCO2e"),
        color=alt.Color(
            "Series:N",
            scale=alt.Scale(
                domain=["Carbon debt remaining", "Cumulative operational savings"],
                range=[C_CARBON, C_SURPLUS]
            ),
            legend=alt.Legend(title="")
        ),
        tooltip=[
            alt.Tooltip("Year:Q"),
            alt.Tooltip("Series:N"),
            alt.Tooltip("tCO2:Q", format=",.1f"),
        ],
    ).properties(
        title=f"Carbon break-even — payback after {payback_yr:.1f} years",
        height=280
    )

    payback_rule = alt.Chart(pd.DataFrame({"Year": [min(payback_yr, 25)]})).mark_rule(
        color=C_DEMAND, strokeDash=[4, 4]
    ).encode(
        x="Year:Q",
        tooltip=[alt.Tooltip("Year:Q", title="Payback year", format=".1f")]
    )
    return chart + payback_rule


def chart_economic(cea_data, selected_buildings, output_mode):
    """
    Cost analysis: payback period and LCOE vs grid price by active PV surface.
    """
    scope = _pv_scope_from_first_total(cea_data, selected_buildings)
    if scope is None:
        return None

    pv_fname = scope["pv_fname"]
    generation_rows = _pv_surface_generation_rows(cea_data, pv_fname, selected_buildings)
    area_rows = _pv_surface_area_rows(cea_data, pv_fname, selected_buildings)
    if not generation_rows:
        return None

    df_gen = pd.DataFrame(generation_rows)
    df_area = pd.DataFrame(area_rows) if area_rows else pd.DataFrame(columns=["Surface", "Area (m2)"])
    df = df_gen.merge(df_area[["Surface", "Area (m2)"]], on="Surface", how="left")
    if df["Area (m2)"].isna().all():
        total_area = scope["area_m2"] or 0
        total_gen = df["kWh"].sum()
        if total_area > 0 and total_gen > 0:
            df["Area (m2)"] = df["kWh"] / total_gen * total_area
    df = df.dropna(subset=["Area (m2)"])
    df = df[(df["Area (m2)"] > 0) & (df["kWh"] > 0)]
    if df.empty:
        return None

    roof_cost_m2, facade_cost_m2 = _panel_costs_for_chart(cea_data)
    grid_price, price_unit = _economic_price_for_chart(cea_data)
    lifetime_years = 25
    discount_rate = 0.05
    o_and_m_rate = 0.01
    crf = (discount_rate * (1 + discount_rate) ** lifetime_years) / (((1 + discount_rate) ** lifetime_years) - 1)

    df["Cost/m2"] = df["Group"].apply(lambda group: roof_cost_m2 if group == "Roof" else facade_cost_m2)
    df["Investment"] = df["Area (m2)"] * df["Cost/m2"]
    df["Annual value"] = df["kWh"] * grid_price
    df["Payback period (years)"] = df["Investment"] / df["Annual value"]
    df["LCOE"] = (df["Investment"] * (crf + o_and_m_rate)) / df["kWh"]
    df = df[
        df["Payback period (years)"].notna()
        & df["LCOE"].notna()
        & (df["Payback period (years)"] < 1_000_000)
        & (df["LCOE"] < 1_000_000)
    ]
    if df.empty:
        return None
    df["Surface"] = pd.Categorical(
        df["Surface"],
        categories=["Roof", "South facade", "East facade", "West facade", "North facade"],
        ordered=True
    )
    df = df.sort_values("Surface")

    color_domain = ["Roof", "South facade", "East facade", "West facade", "North facade"]
    color_range = [C_PV, C_SURPLUS, "#e8b86d", "#a8d5b5", C_NEUTRAL]

    payback = alt.Chart(df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Surface:N", title="", sort=color_domain, axis=alt.Axis(labelAngle=-25)),
        y=alt.Y("Payback period (years):Q", title="Years"),
        color=alt.Color("Surface:N", scale=alt.Scale(domain=color_domain, range=color_range), legend=None),
        tooltip=[
            alt.Tooltip("Surface:N"),
            alt.Tooltip("Payback period (years):Q", format=".1f"),
            alt.Tooltip("Investment:Q", title="Investment", format=",.0f"),
            alt.Tooltip("Annual value:Q", title="Annual value", format=",.0f"),
        ],
    ).properties(title="Simple payback period by PV surface", height=320, width=760)

    lifetime_rule = alt.Chart(pd.DataFrame({"y": [25], "Label": ["25-year panel lifetime"]})).mark_rule(
        color=C_DEMAND, strokeDash=[5, 4]
    ).encode(
        y="y:Q",
        tooltip=[alt.Tooltip("Label:N")]
    )

    lcoe = alt.Chart(df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("Surface:N", title="", sort=color_domain, axis=alt.Axis(labelAngle=-25)),
        y=alt.Y("LCOE:Q", title=price_unit),
        color=alt.Color("Surface:N", scale=alt.Scale(domain=color_domain, range=color_range), legend=None),
        tooltip=[
            alt.Tooltip("Surface:N"),
            alt.Tooltip("LCOE:Q", title=f"LCOE ({price_unit})", format=".3f"),
            alt.Tooltip("kWh:Q", title="Generation (kWh/year)", format=",.0f"),
            alt.Tooltip("Area (m2):Q", title="PV area (m2)", format=",.1f"),
        ],
    ).properties(title="LCOE by PV surface vs grid price", height=320, width=760)

    grid_rule = alt.Chart(pd.DataFrame({"y": [grid_price], "Label": [f"Grid price: {grid_price:.2f} {price_unit}"]})).mark_rule(
        color=C_CARBON, strokeDash=[5, 4]
    ).encode(
        y="y:Q",
        tooltip=[alt.Tooltip("Label:N")]
    )

    return alt.vconcat(payback + lifetime_rule, lcoe + grid_rule, spacing=26)


def chart_seasonal_patterns(cea_data, selected_buildings, output_mode):
    """
    Seasonal patterns — line chart, x=seasons, one line per surface.
    """
    df = None
    if selected_buildings:
        df = cea_data["files"].get("solar_irradiation_seasonally_buildings.csv")
    if df is None:
        df = cea_data["files"].get("solar_irradiation_seasonally.csv")
    if df is None:
        df = cea_data["files"].get("solar_irradiation_seasonally_buildings.csv")
    if df is None:
        pv_fname = next((k for k in cea_data["files"]
                         if k.startswith("PV_PV") and "_total.csv" in k
                         and "buildings" not in k), None)
        if pv_fname:
            df_pv = cea_data["files"].get(pv_fname)
            gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen") if df_pv is not None else None
            date_col = _find_col(df_pv, "date", "Date", "time") if df_pv is not None else None
            if df_pv is not None and gen_col and date_col:
                work = df_pv.copy()
                work["_dt"] = pd.to_datetime(work[date_col], utc=True, errors="coerce")
                work["_month"] = work["_dt"].dt.month
                season_map = {
                    12: "Winter", 1: "Winter", 2: "Winter",
                    3: "Spring", 4: "Spring", 5: "Spring",
                    6: "Summer", 7: "Summer", 8: "Summer",
                    9: "Autumn", 10: "Autumn", 11: "Autumn",
                }
                work["Season"] = work["_month"].map(season_map)
                df_season = (
                    work.groupby("Season")[gen_col]
                    .sum()
                    .reindex(["Spring", "Summer", "Autumn", "Winter"], fill_value=0)
                    .reset_index()
                )
                df_season.columns = ["Season", "PV generation (MWh)"]
                df_season["PV generation (MWh)"] = df_season["PV generation (MWh)"] / 1000
                return alt.Chart(df_season).mark_line(point=True, strokeWidth=2, color=C_PV).encode(
                    x=alt.X("Season:N", sort=["Spring", "Summer", "Autumn", "Winter"], title="Season"),
                    y=alt.Y("PV generation (MWh):Q", title="MWh"),
                    tooltip=["Season", alt.Tooltip("PV generation (MWh):Q", format=",.1f")]
                ).properties(title="Seasonal PV generation pattern", height=280)
        return None

    df = df.copy()
    name_col = _find_col(df, "name", "Name", "building")
    if selected_buildings and name_col:
        df = df[df[name_col].isin(selected_buildings)]
    if df.empty:
        return None

    period_col = _season_col(df)
    surface_map = {
        "Roof":       next((c for c in df.columns if "roof" in c.lower() and "window" not in c.lower()), None),
        "South wall": next((c for c in df.columns if "south" in c.lower() and "window" not in c.lower()), None),
        "East wall":  next((c for c in df.columns if "east" in c.lower() and "window" not in c.lower()), None),
        "West wall":  next((c for c in df.columns if "west" in c.lower() and "window" not in c.lower()), None),
        "North wall": next((c for c in df.columns if "north" in c.lower() and "window" not in c.lower()), None),
    }
    found = {k: v for k, v in surface_map.items() if v is not None}
    if not found or period_col is None:
        return None

    rows = []
    for season, group in df.groupby(period_col):
        for surface, col in found.items():
            rows.append({
                "Season": str(season).strip().title(),
                "Surface": surface,
                "Irradiation (kWh)": float(_num(group[col]).sum())
            })
    df_long = pd.DataFrame(rows)

    surface_order = [s for s in ["Roof", "South wall", "East wall", "West wall", "North wall"] if s in found]
    color_range   = [C_PV, C_SURPLUS, "#e8b86d", "#a8d5b5", C_NEUTRAL][:len(surface_order)]

    chart = alt.Chart(df_long).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("Season:N", sort=["Spring", "Summer", "Autumn", "Winter"], title="Season"),
        y=alt.Y("Irradiation (kWh):Q", title="Annual irradiation (kWh/yr)"),
        color=alt.Color("Surface:N", scale=alt.Scale(domain=surface_order, range=color_range),
                        legend=alt.Legend(title="Surface")),
        tooltip=["Season", "Surface", alt.Tooltip("Irradiation (kWh):Q", format=",.0f", title="kWh/yr")]
    ).properties(title="Solar irradiation by surface — seasonal patterns", height=260)
    return chart


def chart_daily_patterns(cea_data, selected_buildings, output_mode):
    """
    Daily patterns — average 24-hour profile, one line per surface.
    """
    df = cea_data["files"].get("solar_irradiation_hourly.csv")
    if df is None:
        df = cea_data["files"].get("solar_irradiation_daily.csv")
    if df is None:
        pv_fname = next((k for k in cea_data["files"]
                         if k.startswith("PV_PV") and "_total.csv" in k
                         and "buildings" not in k), None)
        if pv_fname:
            df_pv = cea_data["files"].get(pv_fname)
            gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen") if df_pv is not None else None
            date_col = _find_col(df_pv, "date", "Date", "time") if df_pv is not None else None
            if df_pv is not None and gen_col and date_col:
                work = df_pv.copy()
                work["_dt"] = pd.to_datetime(work[date_col], utc=True, errors="coerce")
                work["_hour"] = work["_dt"].dt.hour
                hourly = _num(work[gen_col]).groupby(work["_hour"]).mean().reindex(range(24), fill_value=0) / 1000
                df_hour = pd.DataFrame({"Hour": hourly.index, "Average PV generation (MWh)": hourly.values})
                return alt.Chart(df_hour).mark_area(
                    color=C_PV, opacity=0.42, line={"color": C_PV, "strokeWidth": 2}
                ).encode(
                    x=alt.X("Hour:Q", title="Hour of day", scale=alt.Scale(domain=[0, 23]),
                            axis=alt.Axis(tickMinStep=1)),
                    y=alt.Y("Average PV generation (MWh):Q", title="MWh (average hour)"),
                    tooltip=["Hour", alt.Tooltip("Average PV generation (MWh):Q", format=",.3f")]
                ).properties(title="Average daily PV generation profile", height=280)
        return None

    hour_col = _find_col(df, "hour", "Hour")
    time_col = _find_col(df, "date", "Date", "DATE", "time", "Time")
    surface_map = {
        "Roof":       next((c for c in df.columns if "roof" in c.lower() and "window" not in c.lower()), None),
        "South wall": next((c for c in df.columns if "south" in c.lower() and "window" not in c.lower()), None),
        "East wall":  next((c for c in df.columns if "east" in c.lower() and "window" not in c.lower()), None),
        "West wall":  next((c for c in df.columns if "west" in c.lower() and "window" not in c.lower()), None),
        "North wall": next((c for c in df.columns if "north" in c.lower() and "window" not in c.lower()), None),
    }
    found = {k: v for k, v in surface_map.items() if v is not None}
    if not found or (time_col is None and hour_col is None):
        return None

    df = df.copy()
    if time_col is not None:
        df["_dt"] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
        df["_hour"] = df["_dt"].dt.hour
        if df["_hour"].notna().sum() == 0 and hour_col is not None:
            df["_hour"] = pd.to_numeric(df[hour_col], errors="coerce")
    else:
        df["_hour"] = pd.to_numeric(df[hour_col], errors="coerce")
    df = df[df["_hour"].notna()]
    if df.empty:
        return None
    df["_hour"] = df["_hour"].astype(int)
    if df["_hour"].max() > 23:
        df["_hour"] = df["_hour"] % 24

    rows = []
    for _, row in df.iterrows():
        for surface, col in found.items():
            rows.append({
                "Hour": row["_hour"],
                "Surface": surface,
                "Irradiation (kWh)": float(pd.to_numeric(pd.Series([row[col]]), errors="coerce").fillna(0).iloc[0])
            })
    df_long = pd.DataFrame(rows)
    df_long = (
        df_long.groupby(["Hour", "Surface"], as_index=False)["Irradiation (kWh)"]
        .mean()
    )
    full_hours = pd.MultiIndex.from_product(
        [range(24), df_long["Surface"].unique()],
        names=["Hour", "Surface"]
    ).to_frame(index=False)
    df_long = full_hours.merge(df_long, on=["Hour", "Surface"], how="left")
    df_long["Irradiation (kWh)"] = df_long["Irradiation (kWh)"].fillna(0)

    surface_order = [s for s in ["Roof", "South wall", "East wall", "West wall", "North wall"] if s in found]
    color_range   = [C_PV, C_SURPLUS, "#e8b86d", "#a8d5b5", C_NEUTRAL][:len(surface_order)]

    chart = alt.Chart(df_long).mark_line(strokeWidth=2).encode(
        x=alt.X("Hour:Q", title="Hour of day", scale=alt.Scale(domain=[0, 23]),
                axis=alt.Axis(tickMinStep=1)),
        y=alt.Y("Irradiation (kWh):Q", title="Average hourly irradiation (kWh)"),
        color=alt.Color("Surface:N", scale=alt.Scale(domain=surface_order, range=color_range),
                        legend=alt.Legend(title="Surface")),
        tooltip=["Hour", "Surface", alt.Tooltip("Irradiation (kWh):Q", format=",.1f")]
    ).properties(title="Average daily irradiation profile by surface", height=260)
    return chart


# ── Skill → chart router ──────────────────────────────────────────────────────

SKILL_CHART_MAP = {
    # Solar irradiation group
    "site-potential--solar-availability--surface-irradiation":              chart_solar_irradiation,
    "site-potential--solar-availability--temporal-availability--seasonal-patterns": chart_seasonal_patterns,
    "site-potential--solar-availability--temporal-availability--daily-patterns":    chart_daily_patterns,
    "site-potential--envelope-suitability":                                 chart_solar_irradiation,
    "site-potential--massing-and-shading-strategy":                         chart_massing_shading,
    # Energy generation
    "performance-estimation--energy-generation":                            chart_energy_generation,
    "performance-estimation--panel-type-tradeoff":                          chart_panel_type_tradeoff,
    "optimize-my-design--panel-type-tradeoff":                              chart_panel_type_tradeoff,
    "optimize-my-design--surface-prioritization":                           chart_energy_generation,
    "optimize-my-design--envelope-simplification":                          chart_energy_generation,
    "optimize-my-design--construction-and-integration":                     chart_energy_generation,
    # Self-sufficiency
    "performance-estimation--self-sufficiency":                             chart_self_sufficiency,
    # Carbon
    "impact-and-viability--carbon-impact--carbon-footprint":                chart_carbon_footprint,
    "impact-and-viability--carbon-impact--operational-carbon-footprint":    chart_carbon_footprint,
    "impact-and-viability--carbon-impact--carbon-payback":                  chart_carbon,
    # Economic
    "impact-and-viability--economic-viability--cost-analysis":              chart_economic,
    "impact-and-viability--economic-viability--investment-payback":         chart_economic,
}


def render_skill_chart(skill_id, cea_data, selected_buildings, output_mode):
    """
    Main entry point. Returns an Altair chart or None if no chart applies.
    Call this from app.py — it handles routing and exceptions.
    """
    fn = SKILL_CHART_MAP.get(skill_id)
    if fn is None:
        return None
    return fn(cea_data, selected_buildings, output_mode)
