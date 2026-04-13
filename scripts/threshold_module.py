"""
Radiation threshold calculator for BIPV.

Primary method: Happle et al. 2019 (Equation 1)
  em_BIPV(I) = EmBIPV / (I × η_BIPV × PR_BIPV × A_BIPV × LT_BIPV)
  Threshold = irradiation at which em_BIPV = em_grid
  → I_threshold = EmBIPV / (em_grid × η_BIPV × PR_BIPV × LT_BIPV)

Secondary method: ACACIA curve lookup (ETH Zürich)
  Fetches pre-computed LCA impact vs irradiance curves and finds
  the zero crossing — used for visualization only.

Reference table: McCarty et al. 2025
  "Watt's the Limit?" CISBAT, J. Phys. Conf. Ser. 3140 032006
  Provides threshold values per location × technology × metric
  (Yspec, carbon intensity, CPP) for contextualisation.

All inputs are read from the CEA project zip automatically:
  - Grid emissions  → EPW weather file country code → GRID_INTENSITY lookup
  - Panel types     → detected from PV_PV{n}_* filenames in the zip
  - CEA threshold   → read from scenario config if present
"""

import numpy as np
import requests

# ── Panel constants ──────────────────────────────────────────────────────────
# Source: CEA4 PHOTOVOLTAIC_PANELS.csv (jmccarty CACTUS, ETH Zürich, 2024)
# Embodied carbon consistent with Galimshina et al. (2024), Renewable Energy 236, 121404
# PR = 0.75 per Galimshina 2024; LT = 25yr as in CEA database

PR_BIPV = 0.75
LT_BIPV = 25

PV_PANEL_TYPES = {
    "PV1": {
        "description": "Monocrystalline Si (cSi)",
        "em_bipv": 255.77,   # kgCO2eq/m²
        "eta": 0.1846,       # panel efficiency
        "acacia_key": "monocrystalline",
    },
    "PV2": {
        "description": "Multicrystalline Si (mcSi)",
        "em_bipv": 191.18,
        "eta": 0.1750,
        "acacia_key": "monocrystalline",
    },
    "PV3": {
        "description": "Cadmium Telluride (CdTe)",
        "em_bipv": 47.55,
        "eta": 0.1760,
        "acacia_key": "cdte",
    },
    "PV4": {
        "description": "CIGS",
        "em_bipv": 75.91,
        "eta": 0.0994,
        "acacia_key": "cigs",
    },
}

DEFAULT_PANEL = "PV1"

# ── Grid intensity lookup ────────────────────────────────────────────────────
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

# EPW country code → canonical country name
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

# ── McCarty 2025 reference table ─────────────────────────────────────────────
# All values in kWh/m²/year
# Source: McCarty et al. 2025, J. Phys. Conf. Ser. 3140 032006

MCCARTY_2025 = {
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

# ── ACACIA curve lookup ───────────────────────────────────────────────────────
# Used for visualization only — fetches pre-computed LCA impact vs irradiance curves

ACACIA_CURVE_URL = "https://acacia.arch.ethz.ch/static/data/static_curve_data.json"


def fetch_acacia_curves() -> dict | None:
    """Fetch ACACIA static curve data. Returns None on failure."""
    try:
        r = requests.get(ACACIA_CURVE_URL, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _nearest_key(obj: dict, value: float) -> str:
    keys = sorted([float(k) for k in obj.keys()])
    return f"{min(keys, key=lambda k: abs(k - value)):.2f}"


def get_acacia_curve(panel_type: str, em_grid: float, self_consumption: float = 0.5) -> dict | None:
    """
    Fetch the ACACIA LCA impact curve for a given panel type and grid emissions.
    Returns dict with irradiance and impact arrays, or None if unavailable.
    self_consumption is derived from PV + demand CSVs in the zip.
    """
    data = fetch_acacia_curves()
    if data is None:
        return None

    acacia_key = PV_PANEL_TYPES.get(panel_type, PV_PANEL_TYPES[DEFAULT_PANEL])["acacia_key"]
    panel_key = next(
        (k for k in data if k.lower().replace(" ", "") == acacia_key),
        list(data.keys())[0]
    )
    grid_key = _nearest_key(data[panel_key], em_grid)
    sc_key   = _nearest_key(data[panel_key][grid_key], self_consumption)
    series   = data[panel_key][grid_key][sc_key]

    return {
        "irradiance": np.array(series["Irradiance"]),
        "impact":     np.array(series["Impact"]),
        "panel_key":  panel_key,
        "grid_key":   float(grid_key),
        "sc_key":     float(sc_key),
    }


# ── EPW parsing ───────────────────────────────────────────────────────────────

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

    cc = result["country_code"].upper()
    if cc in EPW_COUNTRY_MAP:
        result["country"] = EPW_COUNTRY_MAP[cc]
    else:
        city = result["city"].lower()
        if any(x in city for x in ["shanghai", "beijing", "shenzhen", "guangzhou"]):
            result["country"] = "China"
        elif any(x in city for x in ["zurich", "zug", "bern", "geneva", "basel"]):
            result["country"] = "Switzerland"
        elif any(x in city for x in ["singapore"]):
            result["country"] = "Singapore"

    return result


# ── Threshold calculation ─────────────────────────────────────────────────────

def calculate_threshold(em_grid: float, panel_type: str = None, capped: bool = True) -> float:
    """
    Calculate radiation threshold using Happle et al. 2019 Equation 1.
    I_threshold = EmBIPV / (em_grid × η_BIPV × PR_BIPV × LT_BIPV)

    Panel-specific embodied carbon and efficiency from CEA4 database
    (Galimshina et al. 2024, ETH Zürich). Returns kWh/m²/year.
    If capped=True, result is bounded between 800–1200 (practical BIPV range
    per McCarty et al. 2025). If capped=False, returns raw formula result.
    """
    panel = PV_PANEL_TYPES.get(panel_type or DEFAULT_PANEL, PV_PANEL_TYPES[DEFAULT_PANEL])
    em_bipv = panel["em_bipv"]
    eta = panel["eta"]

    denominator = em_grid * eta * PR_BIPV * LT_BIPV
    if denominator <= 0:
        return 800
    threshold = em_bipv / denominator
    if capped:
        threshold = max(800, min(1200, threshold))
    return round(threshold, 0)


def calculate_thresholds_all_panels(em_grid: float) -> dict:
    """Calculate capped threshold for all 4 panel types."""
    return {
        ptype: calculate_threshold(em_grid, ptype, capped=True)
        for ptype in PV_PANEL_TYPES
    }


def calculate_thresholds_all_panels_uncapped(em_grid: float) -> dict:
    """Calculate raw (uncapped) threshold for all 4 panel types."""
    return {
        ptype: calculate_threshold(em_grid, ptype, capped=False)
        for ptype in PV_PANEL_TYPES
    }


def get_mccarty_context(em_grid: float, panel_type: str) -> dict:
    """
    Find the closest McCarty 2025 reference location for a given grid emission value
    and return the corresponding threshold values for the panel technology.
    """
    tech_key = (
        "cdte" if PV_PANEL_TYPES.get(panel_type, {}).get("acacia_key") == "cdte" else
        "opv"  if PV_PANEL_TYPES.get(panel_type, {}).get("acacia_key") == "organic" else
        "csi"
    )
    loc_name, loc_data = min(
        MCCARTY_2025.items(),
        key=lambda kv: abs(kv[1]["grid_kgco2_kwh"] - em_grid)
    )
    return {
        "location":         loc_name,
        "grid_reference":   loc_data["grid_kgco2_kwh"],
        "yspec":            loc_data[tech_key]["yspec"],
        "carbon_intensity": loc_data[tech_key]["carbon_intensity"],
        "cpp_10yr":         loc_data[tech_key]["cpp_10yr"],
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def get_threshold_check(weather_header: str, cea_default: float = 800,
                        self_consumption: float = 0.5) -> dict:
    """
    Full threshold check for a given CEA project location.
    Returns dict with all info needed to render the UI and inform the LLM.

    Args:
        weather_header:   First line of the EPW file (LOCATION,...)
        cea_default:      The threshold value currently set in CEA (kWh/m²/year)
        self_consumption: Fraction derived from PV + demand CSVs in the zip
    """
    location = parse_epw_location(weather_header)
    country  = location["country"]
    em_grid  = GRID_INTENSITY.get(country)

    if em_grid is None:
        return {
            "location": location,
            "country": country,
            "em_grid": None,
            "recommended_threshold": None,
            "thresholds_by_panel": None,
            "thresholds_uncapped": None,
            "mccarty": None,
            "acacia_curves": None,
            "cea_threshold": cea_default,
            "match": None,
            "error": f"Grid intensity not found for '{country}'",
        }

    thresholds          = calculate_thresholds_all_panels(em_grid)
    thresholds_uncapped = calculate_thresholds_all_panels_uncapped(em_grid)
    recommended         = thresholds[DEFAULT_PANEL]
    match               = abs(recommended - cea_default) < 50

    # ACACIA curves for all simulated panels (for visualization)
    acacia_curves = {}
    for ptype in PV_PANEL_TYPES:
        curve = get_acacia_curve(ptype, em_grid, self_consumption)
        if curve:
            acacia_curves[ptype] = curve

    # McCarty 2025 context for default panel
    mccarty = get_mccarty_context(em_grid, DEFAULT_PANEL)

    return {
        "location":             location,
        "country":              country,
        "em_grid":              em_grid,
        "recommended_threshold": recommended,
        "thresholds_by_panel":  thresholds,
        "thresholds_uncapped":  thresholds_uncapped,
        "mccarty":              mccarty,
        "acacia_curves":        acacia_curves,
        "cea_threshold":        cea_default,
        "match":                match,
        "error":                None,
    }


# ── Skills where threshold is relevant ───────────────────────────────────────

THRESHOLD_RELEVANT_SKILLS = {
    "site-potential--solar-availability--surface-irradiation",
    "site-potential--solar-availability--temporal-availability--seasonal-patterns",
    "site-potential--solar-availability--temporal-availability--daily-patterns",
    "site-potential--envelope-suitability",
    "site-potential--massing-and-shading-strategy",
    "performance-estimation--energy-generation",
    "performance-estimation--self-sufficiency",
    "impact-and-viability--carbon-impact--operational-carbon-footprint",
    "impact-and-viability--carbon-impact--carbon-payback",
    "impact-and-viability--economic-viability--cost-analysis",
    "impact-and-viability--economic-viability--investment-payback",
    "optimize-my-design--panel-type-tradeoff",
    "optimize-my-design--surface-prioritization",
}


if __name__ == "__main__":
    header = "LOCATION,Inducity-Zug,-,-,MN7,999,47.176,8.513,1,422"
    result = get_threshold_check(header)
    print(f"Location: {result['location']['city']}, {result['country']}")
    print(f"Grid intensity: {result['em_grid']} kgCO2/kWh")
    print(f"CEA default threshold: {result['cea_threshold']} kWh/m²/year")
    print(f"Recommended threshold: {result['recommended_threshold']} kWh/m²/year")
    print(f"Match: {result['match']}")
    if result["mccarty"]:
        print(f"McCarty closest location: {result['mccarty']['location']}")
        print(f"McCarty CPP 10yr: {result['mccarty']['cpp_10yr']} kWh/m²/year")
