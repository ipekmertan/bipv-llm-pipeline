"""
Radiation-threshold guidance for CEA photovoltaic-panel simulations.

CEA's own learning-camp workflow treats 800 kWh/m2/year as the default
quick rule-of-thumb for annual-radiation-threshold. It recommends testing
0, 200, 400, 600 and 800 kWh/m2/year and choosing from the resulting
cost/yield trade-off.

This app does not hardcode the example threshold. It calculates a project-
specific carbon-parity irradiation threshold from the selected PV panel type
and the local grid carbon intensity. That follows Happle et al. (2019) and
McCarty et al. (2025): the irradiation threshold depends on the performance
target. For carbon screening, grid carbon intensity, embodied carbon,
efficiency, performance ratio and lifetime are the primary drivers. Cost/LCOE
is a separate economic threshold and is kept secondary.
"""

from __future__ import annotations

# BIPV panel constants per panel type
# Source: CEA4 PHOTOVOLTAIC_PANELS.csv (jmccarty CACTUS, ETH Zürich, 2024)
# Embodied carbon values consistent with Galimshina et al. (2024),
#   Renewable Energy 236, 121404
# PR = 0.75 per Galimshina 2024; LT = 25yr as in CEA database
import json
from pathlib import Path

try:
    import requests
except Exception:
    requests = None

PR_BIPV = 0.75
LT_BIPV = 25
DISCOUNT_RATE = 0.05
FIXED_OM_RATE = 0.01
VARIABLE_OM_PER_KWH = 0.0
CEA_REFERENCE_THRESHOLD = 800
CEA_ITERATION_THRESHOLDS = [0, 200, 400, 600, 800]
CEA_RECOMMENDED_THRESHOLD = 600
FACADE_EMPTY_RISK_THRESHOLD = 800

PV_PANEL_TYPES = {
    "PV1": {
        "description": "Monocrystalline Si (cSi)",
        "em_bipv": 255.77,   # kgCO2eq/m²
        "eta": 0.1846,       # efficiency
        "roof_cost_ref": 254.7,
        "facade_cost_ref": 345.7,
    },
    "PV2": {
        "description": "Multicrystalline Si (mcSi)",
        "em_bipv": 191.18,
        "eta": 0.1750,
        "roof_cost_ref": 238.6,
        "facade_cost_ref": 329.6,
    },
    "PV3": {
        "description": "Cadmium Telluride (CdTe)",
        "em_bipv": 47.55,
        "eta": 0.1760,
        "roof_cost_ref": 239.5,
        "facade_cost_ref": 330.5,
    },
    "PV4": {
        "description": "CIGS",
        "em_bipv": 75.91,
        "eta": 0.0994,
        "roof_cost_ref": 265.1,
        "facade_cost_ref": 356.1,
    },
}

PANEL_TO_ACACIA = {
    "PV1": "monocrystalline",
    "PV2": "monocrystalline",
    "PV3": "cdte",
    "PV4": "cigs",
}

# Default fallback (PV1 = mono-Si, most common)
DEFAULT_PANEL = "PV1"

# IEA 2023 grid carbon intensity by country (kgCO2/kWh)
# Sources: IEA Electricity Information 2023, Our World in Data, Ember Climate
GRID_INTENSITY = {
    # Europe
    "Albania": 0.020, "Andorra": 0.050, "Austria": 0.107, "Belarus": 0.288,
    "Belgium": 0.163, "Bosnia and Herzegovina": 0.822, "Bulgaria": 0.367,
    "Croatia": 0.176, "Cyprus": 0.626, "Czech Republic": 0.414,
    "Denmark": 0.142, "Estonia": 0.435, "Finland": 0.072, "France": 0.052,
    "Germany": 0.385, "Greece": 0.428, "Hungary": 0.218, "Iceland": 0.028,
    "Ireland": 0.295, "Italy": 0.280, "Kosovo": 0.798, "Latvia": 0.109,
    "Liechtenstein": 0.030, "Lithuania": 0.178, "Luxembourg": 0.129,
    "Malta": 0.467, "Moldova": 0.471, "Monaco": 0.052, "Montenegro": 0.351,
    "Netherlands": 0.270, "North Macedonia": 0.622, "Norway": 0.026,
    "Poland": 0.635, "Portugal": 0.138, "Romania": 0.238, "Russia": 0.322,
    "Serbia": 0.567, "Slovakia": 0.138, "Slovenia": 0.218, "Spain": 0.167,
    "Sweden": 0.041, "Switzerland": 0.042, "Turkey": 0.369, "Ukraine": 0.198,
    "United Kingdom": 0.207,
    # Asia
    "Afghanistan": 0.350, "Armenia": 0.177, "Azerbaijan": 0.459,
    "Bahrain": 0.683, "Bangladesh": 0.565, "Bhutan": 0.020,
    "Brunei": 0.752, "Cambodia": 0.412, "China": 0.581, "Georgia": 0.120,
    "Hong Kong": 0.630, "India": 0.708, "Indonesia": 0.760,
    "Iran": 0.517, "Iraq": 0.680, "Israel": 0.470, "Japan": 0.462,
    "Jordan": 0.480, "Kazakhstan": 0.749, "Kuwait": 0.680,
    "Kyrgyzstan": 0.105, "Laos": 0.120, "Lebanon": 0.680,
    "Malaysia": 0.585, "Maldives": 0.680, "Mongolia": 0.980,
    "Myanmar": 0.295, "Nepal": 0.020, "North Korea": 0.680,
    "Oman": 0.579, "Pakistan": 0.371, "Palestine": 0.680,
    "Philippines": 0.558, "Qatar": 0.490, "Saudi Arabia": 0.680,
    "Singapore": 0.408, "South Korea": 0.415, "Sri Lanka": 0.499,
    "Syria": 0.680, "Taiwan": 0.509, "Tajikistan": 0.085,
    "Thailand": 0.513, "Timor-Leste": 0.680, "Turkmenistan": 0.680,
    "United Arab Emirates": 0.408, "Uzbekistan": 0.619,
    "Vietnam": 0.493, "Yemen": 0.680,
    # Americas
    "Argentina": 0.321, "Belize": 0.450, "Bolivia": 0.490,
    "Brazil": 0.100, "Canada": 0.120, "Chile": 0.358, "Colombia": 0.176,
    "Costa Rica": 0.021, "Cuba": 0.680, "Dominican Republic": 0.535,
    "Ecuador": 0.262, "El Salvador": 0.199, "Guatemala": 0.381,
    "Haiti": 0.680, "Honduras": 0.330, "Jamaica": 0.623, "Mexico": 0.441,
    "Nicaragua": 0.327, "Panama": 0.199, "Paraguay": 0.020,
    "Peru": 0.236, "Puerto Rico": 0.550, "Trinidad and Tobago": 0.680,
    "United States": 0.386, "Uruguay": 0.073, "Venezuela": 0.180,
    # Africa
    "Algeria": 0.556, "Angola": 0.290, "Benin": 0.680, "Botswana": 0.980,
    "Burkina Faso": 0.680, "Burundi": 0.040, "Cameroon": 0.210,
    "Cape Verde": 0.450, "Central African Republic": 0.040,
    "Chad": 0.680, "Comoros": 0.680, "Congo": 0.250,
    "Democratic Republic of Congo": 0.025, "Djibouti": 0.680,
    "Egypt": 0.457, "Equatorial Guinea": 0.680, "Eritrea": 0.680,
    "Eswatini": 0.680, "Ethiopia": 0.025, "Gabon": 0.380,
    "Gambia": 0.680, "Ghana": 0.409, "Guinea": 0.250,
    "Guinea-Bissau": 0.680, "Ivory Coast": 0.349, "Kenya": 0.083,
    "Lesotho": 0.040, "Liberia": 0.250, "Libya": 0.680,
    "Madagascar": 0.480, "Malawi": 0.100, "Mali": 0.680,
    "Mauritania": 0.680, "Mauritius": 0.590, "Morocco": 0.581,
    "Mozambique": 0.120, "Namibia": 0.240, "Niger": 0.680,
    "Nigeria": 0.430, "Rwanda": 0.110, "Sao Tome and Principe": 0.680,
    "Senegal": 0.590, "Sierra Leone": 0.250, "Somalia": 0.680,
    "South Africa": 0.928, "South Sudan": 0.680, "Sudan": 0.348,
    "Tanzania": 0.280, "Togo": 0.410, "Tunisia": 0.468,
    "Uganda": 0.056, "Zambia": 0.075, "Zimbabwe": 0.490,
    # Oceania
    "Australia": 0.490, "Fiji": 0.350, "New Zealand": 0.115,
    "Papua New Guinea": 0.500, "Solomon Islands": 0.680,
    "Vanuatu": 0.680,
}

# EPW country name variations → canonical name
EPW_COUNTRY_MAP = {
    "CHN": "China", "CHE": "Switzerland", "DEU": "Germany",
    "FRA": "France", "GBR": "United Kingdom", "USA": "United States",
    "JPN": "Japan", "KOR": "South Korea", "SGP": "Singapore",
    "MYS": "Malaysia", "THA": "Thailand", "IND": "India",
    "BRA": "Brazil", "AUS": "Australia", "CAN": "Canada",
    "NLD": "Netherlands", "BEL": "Belgium", "AUT": "Austria",
    "SWE": "Sweden", "NOR": "Norway", "DNK": "Denmark",
    "FIN": "Finland", "ITA": "Italy", "ESP": "Spain",
    "PRT": "Portugal", "POL": "Poland", "CZE": "Czech Republic",
    "HUN": "Hungary", "ROU": "Romania", "BGR": "Bulgaria",
    "HRV": "Croatia", "SVN": "Slovenia", "SVK": "Slovakia",
    "GRC": "Greece", "TUR": "Turkey", "RUS": "Russia",
    "UKR": "Ukraine", "ZAF": "South Africa", "NGA": "Nigeria",
    "EGY": "Egypt", "MAR": "Morocco", "IDN": "Indonesia",
    "PHL": "Philippines", "VNM": "Vietnam", "PAK": "Pakistan",
    "BGD": "Bangladesh", "IRN": "Iran", "SAU": "Saudi Arabia",
    "ARE": "United Arab Emirates", "NZL": "New Zealand",
    "ARG": "Argentina", "CHL": "Chile", "COL": "Colombia",
    "MEX": "Mexico", "ZUG": "Switzerland",
}



ACACIA_URL = "https://acacia.arch.ethz.ch/static/data/static_curve_data.json"

def fetch_acacia_curves() -> dict | None:
    if requests is None:
        return None
    try:
        r = requests.get(ACACIA_URL, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def _nearest_key(obj: dict, value: float) -> str:
    keys = sorted([float(k) for k in obj.keys()])
    return f"{min(keys, key=lambda k: abs(k - value)):.2f}"

def get_acacia_curve(panel_type: str, em_grid: float, self_consumption: float = 0.5,
                     acacia_data: dict = None) -> dict | None:
    data = acacia_data or fetch_acacia_curves()
    if data is None:
        return None
    acacia_key = PANEL_TO_ACACIA.get(panel_type, "monocrystalline")
    panel_key = next((k for k in data if k.lower() == acacia_key), list(data.keys())[0])
    grid_key = _nearest_key(data[panel_key], em_grid)
    sc_key   = _nearest_key(data[panel_key][grid_key], self_consumption)
    series   = data[panel_key][grid_key][sc_key]
    return {
        "irradiance": [float(x) for x in series["Irradiance"]],
        "impact":     [float(x) for x in series["Impact"]],
        "panel_key":  panel_key,
        "grid_key":   float(grid_key),
        "sc_key":     float(sc_key),
    }

def parse_epw_location(weather_header: str) -> dict:
    """Parse location info from EPW header line."""
    parts = weather_header.split(",")
    result = {"city": "Unknown", "country_code": "", "country": "Unknown",
              "latitude": None, "longitude": None}
    if len(parts) > 1:
        result["city"] = parts[1].strip()
    if len(parts) > 3:
        result["country_code"] = parts[3].strip()
    if len(parts) > 6:
        try: result["latitude"] = float(parts[6])
        except: pass
    if len(parts) > 7:
        try: result["longitude"] = float(parts[7])
        except: pass

    # Try to resolve country name
    cc = result["country_code"].upper()
    if cc in EPW_COUNTRY_MAP:
        result["country"] = EPW_COUNTRY_MAP[cc]
    else:
        # Try city-based lookup for common cases
        city = result["city"].lower()
        if any(x in city for x in ["shanghai", "beijing", "shenzhen", "guangzhou"]):
            result["country"] = "China"
        elif any(x in city for x in ["zurich", "zug", "bern", "geneva", "basel"]):
            result["country"] = "Switzerland"
        elif any(x in city for x in ["singapore"]):
            result["country"] = "Singapore"

    return result


def _safe_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def capital_recovery_factor(discount_rate: float = DISCOUNT_RATE, lifetime: int = LT_BIPV) -> float:
    """Annualise capital cost using the CEA learning-camp Capex_a structure."""
    i = _safe_float(discount_rate, DISCOUNT_RATE)
    lt = int(_safe_float(lifetime, LT_BIPV) or LT_BIPV)
    if lt <= 0:
        lt = LT_BIPV
    if abs(i) < 1e-9:
        return 1 / lt
    return (i * (1 + i) ** lt) / ((1 + i) ** lt - 1)


def solar_resource_benchmark_band(annual_ghi_kwh_m2: float | None) -> dict:
    """
    Location-specific practical band for annual-radiation-threshold.

    Annual GHI describes the available solar resource before orientation,
    shading and facade tilt losses. The band keeps the threshold in a range
    that is neither so low that very weak surfaces pass, nor so high that facade
    BIPV disappears in moderate-resource locations.
    """
    ghi = _safe_float(annual_ghi_kwh_m2)
    if ghi is None or ghi <= 0:
        return {
            "annual_ghi_kwh_m2": None,
            "lower": 500,
            "upper": FACADE_EMPTY_RISK_THRESHOLD,
            "basis": "fallback band: annual GHI unavailable",
        }

    lower = max(350, 0.45 * ghi)
    upper = max(lower + 150, 0.70 * ghi)
    lower = min(lower, 900)
    upper = min(max(upper, FACADE_EMPTY_RISK_THRESHOLD), 1400)
    return {
        "annual_ghi_kwh_m2": round(ghi, 1),
        "lower": round(lower / 10) * 10,
        "upper": round(upper / 10) * 10,
        "basis": "45-70% of annual GHI, bounded for practical facade screening",
    }


def _resolve_threshold_with_solar_band(carbon_value: float | None, economic_value: float | None, band: dict) -> tuple[float | None, str]:
    """
    Resolve carbon and LCOE thresholds against the local solar-resource band.

    Rule:
    - if either carbon or LCOE falls below the lower benchmark, use the lower benchmark
    - only if both carbon and LCOE are above the upper benchmark, use the upper benchmark
    - otherwise use the value that sits inside the benchmark band
    """
    lower = band.get("lower")
    upper = band.get("upper")
    if lower is None or upper is None:
        return carbon_value if carbon_value is not None else economic_value, "unbounded"

    values = [v for v in [carbon_value, economic_value] if v is not None]
    if not values:
        return None, "unavailable"
    if any(v < lower for v in values):
        return lower, "lower_benchmark"
    if all(v > upper for v in values):
        return upper, "upper_benchmark"
    for v in values:
        if lower <= v <= upper:
            return v, "within_benchmark"
    return min(max(values[0], lower), upper), "bounded"


def _surface_weighted_cost(panel_type: str, economic_inputs: dict | None = None) -> tuple[float, str]:
    """
    Estimate local installed BIPV cost for this panel type.

    The economic context supplies local installed roof/facade cost bands in the
    location currency. The panel database supplies relative panel-type cost
    differences, so the result remains location-currency while still respecting
    PV1/PV2/PV3/PV4 cost differences.
    """
    economic_inputs = economic_inputs or {}
    panel = PV_PANEL_TYPES.get(panel_type or DEFAULT_PANEL, PV_PANEL_TYPES[DEFAULT_PANEL])
    base = PV_PANEL_TYPES[DEFAULT_PANEL]

    roof_cost = _safe_float(economic_inputs.get("roof_cost_m2"))
    facade_cost = _safe_float(economic_inputs.get("facade_cost_m2"))
    if roof_cost is None and facade_cost is None:
        roof_cost, facade_cost = 300.0, 500.0
    elif roof_cost is None:
        roof_cost = facade_cost
    elif facade_cost is None:
        facade_cost = roof_cost

    roof_factor = panel.get("roof_cost_ref", base["roof_cost_ref"]) / base["roof_cost_ref"]
    facade_factor = panel.get("facade_cost_ref", base["facade_cost_ref"]) / base["facade_cost_ref"]
    roof_cost *= roof_factor
    facade_cost *= facade_factor

    panel_areas = (economic_inputs.get("pv_areas_by_panel") or {}).get(panel_type, {})
    roof_area = _safe_float(panel_areas.get("roof_m2"), 0) or 0
    facade_area = _safe_float(panel_areas.get("facade_m2"), 0) or 0

    if roof_area + facade_area > 0:
        total = roof_area + facade_area
        return ((roof_cost * roof_area + facade_cost * facade_area) / total,
                f"weighted by simulated active area: roof {roof_area:.1f} m², facade {facade_area:.1f} m²")

    on_roof = economic_inputs.get("panel_on_roof")
    on_wall = economic_inputs.get("panel_on_wall")
    if on_roof and not on_wall:
        return roof_cost, "roof cost basis"
    if on_wall and not on_roof:
        return facade_cost, "facade cost basis"
    return (roof_cost + facade_cost) / 2, "average roof/facade cost basis"


def calculate_economic_threshold(panel_type: str = None, economic_inputs: dict | None = None,
                                 self_consumption: float = 0.5) -> dict:
    """
    Calculate the break-even annual-radiation-threshold in kWh/m²/year.

    Per m²:
      annual_energy = irradiation * eta * PR
      LCOE = (Capex_a + Opex_fixed + Opex_var) / annual_energy

    Solving LCOE <= local electricity value gives the threshold irradiation.
    """
    economic_inputs = economic_inputs or {}
    ptype = panel_type or DEFAULT_PANEL
    panel = PV_PANEL_TYPES.get(ptype, PV_PANEL_TYPES[DEFAULT_PANEL])
    eta = panel["eta"]
    pr = _safe_float(economic_inputs.get("performance_ratio"), PR_BIPV)
    lifetime = int(_safe_float(economic_inputs.get("lifetime_years"), LT_BIPV) or LT_BIPV)
    discount_rate = _safe_float(economic_inputs.get("discount_rate"), DISCOUNT_RATE)
    fixed_om_rate = _safe_float(economic_inputs.get("fixed_om_rate"), FIXED_OM_RATE)
    variable_om = _safe_float(economic_inputs.get("variable_om_per_kwh"), VARIABLE_OM_PER_KWH)

    buy_price = _safe_float(economic_inputs.get("electricity_price_kwh"))
    export_price = _safe_float(economic_inputs.get("export_compensation_kwh"))
    if buy_price is None:
        buy_price = 0.20
    if export_price is None:
        export_price = 0.0

    sc = _safe_float(self_consumption, 0.5)
    sc = min(1.0, max(0.0, sc if sc is not None else 0.5))
    value_per_kwh = sc * buy_price + (1 - sc) * export_price

    cost_per_m2, cost_basis = _surface_weighted_cost(ptype, economic_inputs)
    crf = capital_recovery_factor(discount_rate, lifetime)
    annual_capex = cost_per_m2 * crf
    annual_fixed_om = cost_per_m2 * fixed_om_rate
    denominator = (value_per_kwh - variable_om) * eta * pr

    if denominator <= 0:
        threshold = None
    else:
        threshold = (annual_capex + annual_fixed_om) / denominator

    return {
        "panel_type": ptype,
        "description": panel["description"],
        "threshold": round(threshold, 0) if threshold is not None else None,
        "cost_per_m2": round(cost_per_m2, 2),
        "cost_basis": cost_basis,
        "electricity_price_kwh": buy_price,
        "export_compensation_kwh": export_price,
        "value_per_kwh": round(value_per_kwh, 4),
        "self_consumption": sc,
        "eta": eta,
        "performance_ratio": pr,
        "lifetime_years": lifetime,
        "discount_rate": discount_rate,
        "fixed_om_rate": fixed_om_rate,
        "variable_om_per_kwh": variable_om,
        "capital_recovery_factor": round(crf, 5),
        "annual_capex_per_m2": round(annual_capex, 2),
        "annual_fixed_om_per_m2": round(annual_fixed_om, 2),
        "currency": economic_inputs.get("currency", "EUR"),
        "currency_symbol": economic_inputs.get("currency_symbol", "€"),
    }


def calculate_threshold(em_grid: float, panel_type: str = None, target_years: float = LT_BIPV) -> float:
    """
    Calculate a carbon screening threshold using Happle et al. 2019.
    I_threshold = EmBIPV / (em_grid × eta_BIPV × PR_BIPV × target_years)

    Panel-specific embodied carbon and efficiency from CEA4 database
    (Galimshina et al. 2024, ETH Zürich). Returns kWh/m²/year.
    """
    panel = PV_PANEL_TYPES.get(panel_type or DEFAULT_PANEL, PV_PANEL_TYPES[DEFAULT_PANEL])
    em_bipv = panel["em_bipv"]
    eta = panel["eta"]

    years = _safe_float(target_years, LT_BIPV)
    denominator = em_grid * eta * PR_BIPV * years
    if denominator <= 0:
        return CEA_REFERENCE_THRESHOLD
    threshold = em_bipv / denominator
    return round(threshold, 0)


def calculate_thresholds_all_panels(em_grid: float, economic_inputs: dict | None = None,
                                    self_consumption: float = 0.5) -> dict:
    """Return carbon-intensity parity thresholds for all panel types."""
    return {
        ptype: calculate_threshold(em_grid, ptype, target_years=LT_BIPV)
        for ptype in PV_PANEL_TYPES
    }


def calculate_threshold_details_all_panels(em_grid: float, economic_inputs: dict | None = None,
                                           self_consumption: float = 0.5) -> dict:
    """Return full carbon and secondary economic threshold details for all panel types."""
    economic_inputs = economic_inputs or {}
    performance = economic_inputs.get("pv_performance_by_panel") or {}
    return {
        ptype: {
            **calculate_economic_threshold(ptype, economic_inputs, self_consumption),
            "threshold": calculate_threshold(em_grid, ptype, target_years=LT_BIPV),
            "carbon_parity_threshold": calculate_threshold(em_grid, ptype, target_years=LT_BIPV),
            "carbon_payback_10yr_threshold": calculate_threshold(em_grid, ptype, target_years=10),
            "economic_threshold": calculate_economic_threshold(ptype, economic_inputs, self_consumption)["threshold"],
            "em_bipv": PV_PANEL_TYPES.get(ptype, PV_PANEL_TYPES[DEFAULT_PANEL])["em_bipv"],
            "annual_generation_kwh": _safe_float(performance.get(ptype, {}).get("annual_generation_kwh"), 0) or 0,
            "area_m2": _safe_float(performance.get(ptype, {}).get("area_m2"), 0) or 0,
        }
        for ptype in PV_PANEL_TYPES
    }


def _normalise_higher_better(values: dict) -> dict:
    valid = {k: v for k, v in values.items() if v is not None and v > 0}
    if not valid:
        return {k: 0 for k in values}
    max_v = max(valid.values())
    if max_v <= 0:
        return {k: 0 for k in values}
    return {k: max(0, (values.get(k) or 0) / max_v) for k in values}


def _normalise_lower_better(values: dict) -> dict:
    valid = {k: v for k, v in values.items() if v is not None and v > 0}
    if not valid:
        return {k: 0 for k in values}
    min_v = min(valid.values())
    return {k: (min_v / values[k]) if values.get(k) and values[k] > 0 else 0 for k in values}


def select_best_panel(selected_panels: list, threshold_details: dict) -> tuple[str, dict]:
    """
    Choose the best overall simulated PV option for early design.

    This is deliberately not the lowest threshold. It balances actual simulated
    annual generation, lifetime carbon intensity and installed cost. If a project
    has no generation/area data, it falls back to technology efficiency and
    embodied carbon.
    """
    selected = [p for p in selected_panels if p in threshold_details] or [DEFAULT_PANEL]
    generation = {p: threshold_details[p].get("annual_generation_kwh", 0) for p in selected}
    carbon_intensity = {}
    for p in selected:
        d = threshold_details[p]
        gen = d.get("annual_generation_kwh", 0)
        area = d.get("area_m2", 0)
        if gen and area:
            carbon_intensity[p] = (d.get("em_bipv", 0) * area) / (gen * LT_BIPV)
        else:
            carbon_intensity[p] = d.get("em_bipv", 0) / max(d.get("eta", 0.01), 0.01)
    cost = {p: threshold_details[p].get("cost_per_m2", 0) for p in selected}

    generation_score = _normalise_higher_better(generation)
    carbon_score = _normalise_lower_better(carbon_intensity)
    cost_score = _normalise_lower_better(cost)

    scores = {}
    for p in selected:
        scores[p] = (
            0.45 * generation_score.get(p, 0)
            + 0.35 * carbon_score.get(p, 0)
            + 0.20 * cost_score.get(p, 0)
        )

    best = max(scores, key=scores.get)
    return best, {
        "scores": scores,
        "generation_score": generation_score,
        "carbon_score": carbon_score,
        "cost_score": cost_score,
        "carbon_intensity_kgco2_kwh": carbon_intensity,
    }


def calculate_thresholds_all_panels_uncapped(em_grid: float) -> dict:
    """Backward-compatible alias: calculate carbon-parity thresholds for all 4 panel types."""
    return {
        ptype: calculate_threshold(em_grid, ptype, target_years=LT_BIPV)
        for ptype in PV_PANEL_TYPES
    }


def get_threshold_check(weather_header: str, cea_default: float = 800, self_consumption: float = 0.5,
                        acacia_data: dict = None, economic_inputs: dict | None = None) -> dict:
    """
    Full threshold check for a given location.
    Returns dict with all info needed to render the UI boxes.
    """
    location = parse_epw_location(weather_header)
    country = location["country"]

    em_grid = GRID_INTENSITY.get(country, None)

    if em_grid is None:
        return {
            "location": location,
            "country": country,
            "em_grid": None,
            "recommended_threshold": None,
            "cea_threshold": cea_default,
            "match": None,
            "error": f"Grid intensity not found for {country}"
        }

    economic_inputs = economic_inputs or {}
    thresholds = calculate_thresholds_all_panels(em_grid, economic_inputs, self_consumption)
    threshold_details = calculate_threshold_details_all_panels(em_grid, economic_inputs, self_consumption)
    thresholds_uncapped = calculate_thresholds_all_panels_uncapped(em_grid)
    selected_panels = economic_inputs.get("pv_types") or list(PV_PANEL_TYPES.keys())
    selected_panels = [p for p in selected_panels if p in thresholds] or [DEFAULT_PANEL]

    valid_selected = [p for p in selected_panels if thresholds.get(p) is not None]
    threshold_basis = "carbon_parity"
    fallback_reason = None
    benchmark_band = solar_resource_benchmark_band(economic_inputs.get("annual_ghi_kwh_m2"))
    if valid_selected:
        recommended_panel, panel_selection = select_best_panel(valid_selected, threshold_details)
        carbon_value = thresholds[recommended_panel]
        recommended = carbon_value
        outside_solar_band = (
            carbon_value is not None
            and (
                carbon_value < benchmark_band["lower"]
                or carbon_value > benchmark_band["upper"]
            )
        )
        if outside_solar_band:
            economic_value = threshold_details[recommended_panel].get("economic_threshold")
            if economic_value is not None:
                side = "below" if carbon_value < benchmark_band["lower"] else "above"
                resolved_value, resolved_basis = _resolve_threshold_with_solar_band(
                    carbon_value, economic_value, benchmark_band
                )
                fallback_reason = (
                    f"The best overall PV option is {recommended_panel}. Its carbon-parity threshold "
                    f"{carbon_value:.0f} kWh/m2/year is {side} the location-specific solar-resource "
                    f"benchmark band ({benchmark_band['lower']:.0f}-{benchmark_band['upper']:.0f} kWh/m2/year). "
                    f"The LCOE value is {economic_value:.0f} kWh/m2/year, so the displayed value follows "
                    f"the solar-band resolution rule: {resolved_basis}."
                )
                recommended = resolved_value
                threshold_basis = f"solar_band_{resolved_basis}"
    else:
        recommended_panel = DEFAULT_PANEL
        recommended = cea_default
        threshold_basis = "cea_default"
        panel_selection = {}
    match = abs(float(recommended or 0) - cea_default) < 50 if recommended is not None else None

    acacia_curves = {}
    data = acacia_data or fetch_acacia_curves()
    if data:
        for ptype in PV_PANEL_TYPES:
            curve = get_acacia_curve(ptype, em_grid, self_consumption, acacia_data=data)
            if curve:
                acacia_curves[ptype] = curve

    return {
        "location": location,
        "country": country,
        "em_grid": em_grid,
        "recommended_threshold": recommended,
        "recommended_panel": recommended_panel,
        "threshold_basis": threshold_basis,
        "fallback_reason": fallback_reason,
        "solar_resource_benchmark": benchmark_band,
        "panel_selection": panel_selection,
        "thresholds_by_panel": thresholds,
        "threshold_details_by_panel": threshold_details,
        "thresholds_uncapped": thresholds_uncapped,
        "cea_reference_threshold": CEA_REFERENCE_THRESHOLD,
        "cea_iteration_thresholds": CEA_ITERATION_THRESHOLDS,
        "cea_recommended_threshold": CEA_RECOMMENDED_THRESHOLD,
        "facade_empty_risk_threshold": FACADE_EMPTY_RISK_THRESHOLD,
        "economic_inputs": economic_inputs,
        "acacia_curves": acacia_curves,
        "cea_threshold": cea_default,
        "match": match,
        "error": None
    }


# Skills where radiation threshold matters
THRESHOLD_RELEVANT_SKILLS = {
    "site-potential--solar-availability--surface-irradiation",
    "site-potential--solar-availability--temporal-availability--seasonal-patterns",
    "site-potential--solar-availability--temporal-availability--daily-patterns",
    "site-potential--envelope-suitability",
    "site-potential--massing-and-shading-strategy",
    "performance-estimation--energy-generation",
    "performance-estimation--self-sufficiency",
    "performance-estimation--panel-type-tradeoff",
    "impact-and-viability--carbon-impact--carbon-footprint",
    "impact-and-viability--carbon-impact--operational-carbon-footprint",
    "impact-and-viability--carbon-impact--carbon-payback",
    "impact-and-viability--economic-viability--cost-analysis",
    "impact-and-viability--economic-viability--investment-payback",
    "optimize-my-design--panel-type-tradeoff",
    "optimize-my-design--surface-prioritization",
}


if __name__ == "__main__":
    # Test with the Zug weather header from the uploaded zip
    header = "LOCATION,Inducity-Zug,-,-,MN7,999,47.176,8.513,1,422"
    result = get_threshold_check(header)
    print(f"Location: {result['location']['city']}, {result['country']}")
    print(f"Grid intensity: {result['em_grid']} kgCO2/kWh")
    print(f"CEA default threshold: {result['cea_threshold']} kWh/m²/year")
    print(f"Recommended threshold: {result['recommended_threshold']} kWh/m²/year")
    print(f"Match: {result['match']}")

