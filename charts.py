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
    for kw in keywords:
        match = next((c for c in df.columns if kw.lower() in c.lower()), None)
        if match:
            return match
    return None

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


# ── Chart builders ────────────────────────────────────────────────────────────

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
    found = {k: v for k, v in surface_map.items() if v is not None and df_b[v].sum() > 0}

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
                "kWh": float(row[col]) if row[col] == row[col] else 0
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

    monthly = _monthly_from_hourly(df_pv, gen_col)
    if monthly is None:
        return None

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
    ).properties(title="Monthly PV generation", height=200)

    if output_mode == "Key takeaway":
        return monthly_bar

    if output_mode == "Explain the numbers":
        # Add daily profile
        date_col = _find_col(df_pv, "date", "Date", "time")
        if date_col:
            try:
                df_pv["_dt"] = pd.to_datetime(df_pv[date_col], utc=True, errors="coerce")
                df_pv["hour"] = df_pv["_dt"].dt.hour
                hourly_avg = df_pv.groupby("hour")[gen_col].mean() / 1000
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
                ).properties(title="Average daily generation profile", height=200)
                return monthly_bar | profile
            except Exception:
                pass
        return monthly_bar

    if output_mode == "Design implication":
        # Surface contribution from buildings file
        bldg_fname = pv_fname.replace("_total.csv", "_total_buildings.csv")
        df_b = cea_data["files"].get(bldg_fname)
        name_col = _find_col(df_b, "name", "Name") if df_b is not None else None
        gen_b_col = _find_col(df_b, "E_PV_gen", "E_PV") if df_b is not None else None

        if df_b is not None and name_col and gen_b_col:
            if selected_buildings:
                df_b = df_b[df_b[name_col].isin(selected_buildings)]
            df_b = df_b.copy()
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
        monthly_pv = df_pv.groupby("month")[gen_col].sum() / 1000

        if demand_files:
            demand_col = _find_col(demand_files[0], "E_sys", "GRID", "E_tot")
            if demand_col:
                total_demand = sum(d[demand_col].values for d in demand_files
                                   if demand_col in d.columns)
                df_demand = df_pv.copy()
                df_demand["_demand"] = total_demand
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
                    range=[C_SURPLUS, C_CARBON])),
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

            return grouped | surplus_chart

    except Exception:
        return None


def chart_carbon(cea_data, selected_buildings, output_mode):
    """
    Carbon impact skills.
    All modes → carbon payback timeline bar/line combo
    """
    # Need PV area + generation + grid emissions to estimate payback
    pv_fname = next((k for k in cea_data["files"]
                     if k.startswith("PV_PV") and "_total.csv" in k
                     and "buildings" not in k), None)
    if pv_fname is None:
        return None

    df_pv = cea_data["files"][pv_fname]
    gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen")
    area_col = _find_col(df_pv, "area", "m2", "Area")
    if gen_col is None:
        return None

    annual_gen_kwh = df_pv[gen_col].sum()
    if annual_gen_kwh <= 0:
        return None

    # Read grid emissions from GRID.csv
    grid_df = cea_data["files"].get("GRID.csv")
    em_col = _find_col(grid_df, "CO2", "co2", "emission", "GHG") if grid_df is not None else None
    em_grid = float(grid_df[em_col].iloc[0]) if (em_col and grid_df is not None) else 0.4

    # Estimate embodied carbon — use PV panel data if available
    panel_df = cea_data["files"].get("PHOTOVOLTAIC_PANELS.csv")
    em_bipv = 329.0  # default cSi kgCO2/m2
    if panel_df is not None:
        em_col2 = _find_col(panel_df, "CO2", "embodied", "carbon", "GHG")
        if em_col2:
            try:
                em_bipv = float(panel_df[em_col2].iloc[0])
            except Exception:
                pass

    total_area = df_pv[area_col].sum() if area_col else 1000
    embodied_total = em_bipv * total_area  # kgCO2
    annual_avoided = annual_gen_kwh * em_grid  # kgCO2/yr

    if annual_avoided <= 0:
        return None

    payback_yr = embodied_total / annual_avoided
    years = list(range(0, 26))
    cumulative_avoided = [annual_avoided * y / 1000 for y in years]
    embodied_line = [embodied_total / 1000] * len(years)

    df_payback = pd.DataFrame({
        "Year": years,
        "Cumulative avoided (tCO₂)": cumulative_avoided,
        "Embodied carbon (tCO₂)": embodied_line,
    })

    avoided_line = alt.Chart(df_payback).mark_line(
        color=C_SURPLUS, strokeWidth=2
    ).encode(
        x=alt.X("Year:Q", title="Years of operation"),
        y=alt.Y("Cumulative avoided (tCO₂):Q", title="tCO₂"),
        tooltip=["Year", alt.Tooltip("Cumulative avoided (tCO₂):Q", format=".1f")]
    )
    embodied = alt.Chart(df_payback).mark_line(
        color=C_CARBON, strokeDash=[6, 3], strokeWidth=1.5
    ).encode(
        x="Year:Q",
        y=alt.Y("Embodied carbon (tCO₂):Q"),
        tooltip=[alt.Tooltip("Embodied carbon (tCO₂):Q", format=".1f")]
    )

    title = f"Carbon payback — est. {payback_yr:.1f} years"
    chart = (avoided_line + embodied).properties(title=title, height=220)

    if output_mode == "Key takeaway":
        return chart

    # Explain numbers / Design impl — add annual bar alongside
    df_annual = pd.DataFrame({
        "Category": ["Embodied carbon", "Annual avoided (×10yr)", "Annual avoided (×25yr)"],
        "tCO₂": [embodied_total / 1000,
                 annual_avoided * 10 / 1000,
                 annual_avoided * 25 / 1000],
        "color": [C_CARBON, C_PV, C_SURPLUS]
    })
    bar = alt.Chart(df_annual).mark_bar(cornerRadiusTopLeft=3,
                                         cornerRadiusTopRight=3).encode(
        x=alt.X("Category:N", title=""),
        y=alt.Y("tCO₂:Q", title="tCO₂"),
        color=alt.Color("color:N", scale=None, legend=None),
        tooltip=["Category", alt.Tooltip("tCO₂:Q", format=".1f")]
    ).properties(title="Carbon summary", height=220)

    return chart | bar


def chart_economic(cea_data, selected_buildings, output_mode):
    """
    Economic viability skills.
    Key takeaway     → simple payback bar (cost vs savings)
    Explain numbers  → cumulative cashflow line over 25yr
    Design impl.     → cumulative cashflow + cost breakdown
    """
    pv_fname = next((k for k in cea_data["files"]
                     if k.startswith("PV_PV") and "_total.csv" in k
                     and "buildings" not in k), None)
    if pv_fname is None:
        return None

    df_pv = cea_data["files"][pv_fname]
    gen_col = _find_col(df_pv, "E_PV_gen", "E_PV", "gen")
    area_col = _find_col(df_pv, "area", "m2", "Area")
    if gen_col is None:
        return None

    annual_gen_kwh = df_pv[gen_col].sum()
    total_area = df_pv[area_col].sum() if area_col else 1000

    # Rough cost estimate — read from panel data if available
    panel_df = cea_data["files"].get("PHOTOVOLTAIC_PANELS.csv")
    cost_per_m2 = 254.0  # default €/m2 (PV1 roof from McCarty)
    if panel_df is not None:
        cost_col = _find_col(panel_df, "cost", "Cost", "CAPEX", "price")
        if cost_col:
            try:
                cost_per_m2 = float(panel_df[cost_col].iloc[0])
            except Exception:
                pass

    electricity_price = 0.28  # €/kWh typical CH
    total_cost = cost_per_m2 * total_area
    annual_savings = annual_gen_kwh * electricity_price
    payback_yr = total_cost / annual_savings if annual_savings > 0 else 25

    years = list(range(0, 26))
    cashflow = [-total_cost + annual_savings * y for y in years]

    df_cf = pd.DataFrame({"Year": years, "Cumulative cashflow (€)": cashflow})
    df_cf["positive"] = df_cf["Cumulative cashflow (€)"] >= 0

    if output_mode == "Key takeaway":
        df_sum = pd.DataFrame({
            "Item": ["Total investment", "Annual savings (10yr)", "Annual savings (25yr)"],
            "€": [total_cost, annual_savings * 10, annual_savings * 25],
        })
        df_sum["bar_color"] = df_sum["Item"].apply(
            lambda item: C_CARBON if item == "Total investment" else C_SURPLUS
        )
        bar = alt.Chart(df_sum).mark_bar(cornerRadiusTopLeft=3,
                                          cornerRadiusTopRight=3).encode(
            x=alt.X("Item:N", title=""),
            y=alt.Y("€:Q", title="€"),
            color=alt.Color("bar_color:N", scale=None, legend=None),
            tooltip=["Item", alt.Tooltip("€:Q", format=",.0f")]
        ).properties(title=f"Economic summary — est. payback {payback_yr:.1f} yr",
                     height=200)
        return bar

    # Explain numbers / Design impl — cashflow line
    line = alt.Chart(df_cf).mark_line(strokeWidth=2).encode(
        x=alt.X("Year:Q", title="Years"),
        y=alt.Y("Cumulative cashflow (€):Q", title="€"),
        color=alt.condition(
            alt.datum.positive,
            alt.value(C_SURPLUS), alt.value(C_CARBON)
        ),
        tooltip=["Year", alt.Tooltip("Cumulative cashflow (€):Q", format=",.0f")]
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(
        color=C_NEUTRAL, strokeDash=[4, 4]
    ).encode(y="y:Q")

    chart = (line + zero).properties(
        title=f"Cumulative cashflow over 25 years (payback ~{payback_yr:.1f} yr)",
        height=220
    )
    return chart


def chart_seasonal_patterns(cea_data, selected_buildings, output_mode):
    """
    Seasonal patterns — line chart, x=seasons, one line per surface.
    """
    df = cea_data["files"].get("solar_irradiation_seasonally.csv")
    if df is None:
        return None

    period_col = _find_col(df, "period", "season", "Season", "Period")
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
    for _, row in df.iterrows():
        for surface, col in found.items():
            rows.append({
                "Season": row[period_col],
                "Surface": surface,
                "Irradiation (kWh)": float(row[col]) if row[col] == row[col] else 0
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
                "Irradiation (kWh)": float(row[col]) if row[col] == row[col] else 0
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
    "site-potential--massing-and-shading-strategy":                         chart_solar_irradiation,
    # Energy generation
    "performance-estimation--energy-generation":                            chart_energy_generation,
    "optimize-my-design--panel-type-tradeoff":                              chart_energy_generation,
    "optimize-my-design--surface-prioritization":                           chart_energy_generation,
    "optimize-my-design--envelope-simplification":                          chart_energy_generation,
    "optimize-my-design--construction-and-integration":                     chart_energy_generation,
    # Self-sufficiency
    "performance-estimation--self-sufficiency":                             chart_self_sufficiency,
    # Carbon
    "impact-and-viability--carbon-impact--operational-carbon-footprint":    chart_carbon,
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
    try:
        return fn(cea_data, selected_buildings, output_mode)
    except Exception:
        return None
