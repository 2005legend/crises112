"""
sample_dataset.py — Generates data/sample_incidents.json
Run: python sample_dataset.py
Produces 25 pre-geocoded incidents across 5+ Chennai areas (R3-7.1, R3-7.2).
"""
import json
import uuid
import os

INCIDENTS = [
    # Anna Nagar
    {"incident_type": "road_accident", "lat": 13.0878, "lon": 80.2185, "severity_label": "High",   "area_name": "Anna Nagar",       "report_count": 4},
    {"incident_type": "medical",       "lat": 13.0860, "lon": 80.2170, "severity_label": "Critical","area_name": "Anna Nagar",       "report_count": 2},
    {"incident_type": "fire",          "lat": 13.0895, "lon": 80.2200, "severity_label": "High",   "area_name": "Anna Nagar",       "report_count": 3},
    {"incident_type": "crime",         "lat": 13.0845, "lon": 80.2155, "severity_label": "Medium", "area_name": "Anna Nagar",       "report_count": 1},
    {"incident_type": "road_accident", "lat": 13.0910, "lon": 80.2210, "severity_label": "Low",    "area_name": "Anna Nagar",       "report_count": 1},

    # T. Nagar
    {"incident_type": "fire",          "lat": 13.0418, "lon": 80.2341, "severity_label": "Critical","area_name": "T. Nagar",         "report_count": 5},
    {"incident_type": "flood",         "lat": 13.0400, "lon": 80.2320, "severity_label": "High",   "area_name": "T. Nagar",         "report_count": 3},
    {"incident_type": "road_accident", "lat": 13.0435, "lon": 80.2360, "severity_label": "Medium", "area_name": "T. Nagar",         "report_count": 2},
    {"incident_type": "medical",       "lat": 13.0450, "lon": 80.2380, "severity_label": "High",   "area_name": "T. Nagar",         "report_count": 2},
    {"incident_type": "crime",         "lat": 13.0390, "lon": 80.2300, "severity_label": "Low",    "area_name": "T. Nagar",         "report_count": 1},

    # Adyar
    {"incident_type": "flood",         "lat": 13.0012, "lon": 80.2565, "severity_label": "High",   "area_name": "Adyar",            "report_count": 6},
    {"incident_type": "road_accident", "lat": 13.0030, "lon": 80.2580, "severity_label": "Medium", "area_name": "Adyar",            "report_count": 2},
    {"incident_type": "medical",       "lat": 12.9995, "lon": 80.2550, "severity_label": "Critical","area_name": "Adyar",            "report_count": 3},
    {"incident_type": "fire",          "lat": 13.0050, "lon": 80.2600, "severity_label": "High",   "area_name": "Adyar",            "report_count": 2},
    {"incident_type": "crime",         "lat": 13.0070, "lon": 80.2620, "severity_label": "Low",    "area_name": "Adyar",            "report_count": 1},

    # Velachery
    {"incident_type": "flood",         "lat": 12.9815, "lon": 80.2180, "severity_label": "Critical","area_name": "Velachery",        "report_count": 7},
    {"incident_type": "road_accident", "lat": 12.9830, "lon": 80.2200, "severity_label": "High",   "area_name": "Velachery",        "report_count": 4},
    {"incident_type": "medical",       "lat": 12.9800, "lon": 80.2160, "severity_label": "Medium", "area_name": "Velachery",        "report_count": 2},
    {"incident_type": "fire",          "lat": 12.9845, "lon": 80.2220, "severity_label": "High",   "area_name": "Velachery",        "report_count": 3},
    {"incident_type": "crime",         "lat": 12.9860, "lon": 80.2240, "severity_label": "Low",    "area_name": "Velachery",        "report_count": 1},

    # Tambaram
    {"incident_type": "road_accident", "lat": 12.9249, "lon": 80.1000, "severity_label": "High",   "area_name": "Tambaram",         "report_count": 3},
    {"incident_type": "fire",          "lat": 12.9260, "lon": 80.1020, "severity_label": "Medium", "area_name": "Tambaram",         "report_count": 2},
    {"incident_type": "medical",       "lat": 12.9235, "lon": 80.0980, "severity_label": "Critical","area_name": "Tambaram",         "report_count": 4},
    {"incident_type": "flood",         "lat": 12.9270, "lon": 80.1040, "severity_label": "High",   "area_name": "Tambaram",         "report_count": 2},
    {"incident_type": "crime",         "lat": 12.9220, "lon": 80.0960, "severity_label": "Low",    "area_name": "Tambaram",         "report_count": 1},

    # Porur (bonus 6th area)
    {"incident_type": "road_accident", "lat": 13.0358, "lon": 80.1573, "severity_label": "Medium", "area_name": "Porur",            "report_count": 2},
]

def generate():
    records = []
    for inc in INCIDENTS:
        records.append({
            "incident_id": str(uuid.uuid4()),
            "incident_type": inc["incident_type"],
            "lat": inc["lat"],
            "lon": inc["lon"],
            "severity_label": inc["severity_label"],
            "area_name": inc["area_name"],
            "report_count": inc["report_count"],
        })
    return records

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    records = generate()
    out_path = "data/sample_incidents.json"
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)
    areas = {r["area_name"] for r in records}
    print(f"Generated {len(records)} incidents across {len(areas)} areas → {out_path}")
    print(f"Areas: {', '.join(sorted(areas))}")
