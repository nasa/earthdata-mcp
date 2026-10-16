"""Shared mock data for UI mockup demos."""

# --- CMR results used as terra component props ---
# These are real CMR concept IDs + variables for testing
TERRA_SCENARIOS = [
    {
        "label": "Sea Surface Temperature (MUR)",
        "collection": "C2036882064-POCLOUD",
        "variable": "analysed_sst",
        "variableEntryId": "V2112019710-POCLOUD",
        "startDate": "2024-01-01",
        "endDate": "2024-01-31",
        "location": {"lat": 36.0, "lon": -122.0},
        "long_name": "Analysed Sea Surface Temperature",
    },
    {
        "label": "Soil Moisture (SMAP)",
        "collection": "C2208418228-NSIDC_ECS",
        "variable": "soil_moisture",
        "variableEntryId": "V2208418229-NSIDC_ECS",
        "startDate": "2024-01-01",
        "endDate": "2024-01-31",
        "location": {"lat": 40.0, "lon": -105.0},
        "long_name": "Soil Moisture",
    },
]

# Default scenario for single-widget demos
DEFAULT = TERRA_SCENARIOS[0]

# --- Tabular: collection search results for DataTable ---
COLLECTIONS = [
    {"short_name": "MOD11A1",               "title": "MODIS/Terra Land Surface Temperature Daily",     "provider": "LPCLOUD",    "granules": 8432},
    {"short_name": "MUR-JPL-L4-GLOB-v4.1",  "title": "MUR MEaSUREs Sea Surface Temperature",           "provider": "POCLOUD",    "granules": 3214},
    {"short_name": "SPL3SMP",               "title": "SMAP L3 Radiometer Soil Moisture",               "provider": "NSIDC_ECS",  "granules": 2876},
    {"short_name": "GLDAS_NOAH025_3H",      "title": "GLDAS Noah Land Surface Model 0.25deg 3hr",      "provider": "GES_DISC",   "granules": 62140},
    {"short_name": "ASTGTM_NC",             "title": "ASTER Global Digital Elevation Model V003",       "provider": "LPCLOUD",    "granules": 22702},
]

# --- Simple time series for prefab BarChart (no external fetch needed) ---
SST_DATES   = ["2023-01","2023-02","2023-03","2023-04","2023-05","2023-06",
               "2023-07","2023-08","2023-09","2023-10","2023-11","2023-12",
               "2024-01","2024-02","2024-03","2024-04","2024-05","2024-06"]
SST_ANOMALY = [0.2,0.4,0.8,1.1,1.4,1.8,2.1,1.9,1.6,1.3,0.9,0.6,
               0.3,0.5,0.7,1.0,1.2,1.5]
