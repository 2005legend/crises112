import uvicorn
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional

from models import init_db, get_db, Incident
from geocoding import geocode_location, reverse_geocode
from deduplication import get_nearby_incidents_logic, perform_link_incident, haversine


def _cluster_incidents(incidents, zoom: int, reverse_geocode_fn=None):
    """
    Pure clustering logic extracted for testability.
    Returns list of cluster dicts.
    """
    if reverse_geocode_fn is None:
        reverse_geocode_fn = reverse_geocode

    if zoom >= 12:
        return [{
            "cluster_id": inc.id,
            "lat": inc.lat,
            "lon": inc.lon,
            "incident_count": inc.report_count,
            "max_severity_label": inc.severity_label,
            "area_name": inc.area_name
        } for inc in incidents]

    clusters = []
    for inc in incidents:
        matched_cluster = None
        for cl in clusters:
            if haversine(inc.lat, inc.lon, cl["lat"], cl["lon"]) <= 1000.0:
                matched_cluster = cl
                break

        if matched_cluster:
            n = matched_cluster["incident_count"]
            matched_cluster["lat"] = ((matched_cluster["lat"] * n) + inc.lat) / (n + 1)
            matched_cluster["lon"] = ((matched_cluster["lon"] * n) + inc.lon) / (n + 1)
            matched_cluster["incident_count"] += 1
            labels = ["Low", "Medium", "High", "Critical"]
            idx_inc = labels.index(inc.severity_label) if inc.severity_label in labels else 0
            idx_cl = labels.index(matched_cluster["max_severity_label"]) if matched_cluster["max_severity_label"] in labels else 0
            if idx_inc > idx_cl:
                matched_cluster["max_severity_label"] = inc.severity_label
        else:
            clusters.append({
                "cluster_id": f"cluster-{inc.id[:8]}",
                "lat": inc.lat,
                "lon": inc.lon,
                "incident_count": 1,
                "max_severity_label": inc.severity_label,
                "area_name": inc.area_name
            })

    for cl in clusters:
        if not cl["area_name"]:
            a, d, c = reverse_geocode_fn(cl["lat"], cl["lon"])
            cl["area_name"] = a or d or c or "Unknown Area"

    return clusters

app = FastAPI(title="Geo Service (Role 3) - EIFS", port=8002)

@app.on_event("startup")
def startup_event():
    init_db()

# --- Request Schemas ---

class GeocodeRequest(BaseModel):
    location_text: str
    city_hint: Optional[str] = None
    state_hint: Optional[str] = None

class NearbyIncidentsRequest(BaseModel):
    lat: float
    lon: float
    radius_m: int = 500
    within_minutes: int = 30

class LinkIncidentRequest(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    summary: str
    reported_time: str

class ReverseGeocodeRequest(BaseModel):
    lat: float
    lon: float

# --- Endpoints ---

@app.post("/geocode")
def api_geocode(req: GeocodeRequest):
    """R3-1: Geocodes using advanced Nominatim structured querying for high accuracy."""
    
    lat, lon, conf, resolved, landmarks = geocode_location(
        location_text=req.location_text,
        city_hint=req.city_hint,
        state_hint=req.state_hint
    )

    return {
        "lat": lat,
        "lon": lon,
        "confidence": conf,
        "resolved_name": resolved,
        "landmarks": landmarks
    }

@app.post("/nearby-incidents")
def api_nearby_incidents(req: NearbyIncidentsRequest):
    """R3-2: Haversine distance lookup for candidates."""
    candidates = get_nearby_incidents_logic(req.lat, req.lon, req.radius_m, req.within_minutes)
    return candidates

@app.post("/link-incident")
def api_link_incident(req: LinkIncidentRequest):
    """R3-3: Combined Geo + Semantic Incident Linking"""
    incident_id, conf, reason = perform_link_incident(req.lat, req.lon, req.summary, req.reported_time)
    return {
        "incident_id": incident_id,
        "confidence": conf,
        "reason": reason
    }

@app.get("/clusters")
def api_clusters(zoom: int = Query(10, ge=1, le=18), bbox: Optional[str] = None):
    """
    R3-4: Map Cluster Data.
    Groups incidents into clusters for zoom < 12.
    """
    with get_db() as db:
        incidents = db.query(Incident).all()

    return _cluster_incidents(incidents, zoom)

@app.post("/reverse-geocode")
def api_reverse_geocode(req: ReverseGeocodeRequest):
    """R3-5: Reverse Geocoding with ~100m caching."""
    area, district, city = reverse_geocode(req.lat, req.lon)
    return {
        "area_name": area,
        "district": district,
        "city": city
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
