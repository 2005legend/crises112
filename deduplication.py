import math
import datetime
import requests
from typing import List, Dict, Tuple, Optional
from models import get_db, Incident

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000.0 # meters! R3-2 expects meters

def get_nearby_incidents_logic(lat: float, lon: float, radius_m: int = 500, within_minutes: int = 30) -> List[Dict]:
    """
    R3-2: Finds incidents within radius_m and within_minutes timeframe.
    Returns: list of dict sorted by distance ascending.
    """
    candidates = []
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(minutes=within_minutes)
    
    with get_db() as db:
        # Get recent open incidents (mocking 'open' status if available, relying on updated_at)
        recent = db.query(Incident).filter(Incident.updated_at >= cutoff).all()
        for inc in recent:
            dist = haversine(lat, lon, inc.lat, inc.lon)
            if dist <= radius_m:
                candidates.append({
                    "incident_id": inc.id,
                    "distance_m": dist,
                    "summary": inc.summary
                })
                
    # Sort ascending
    candidates.sort(key=lambda x: x["distance_m"])
    return candidates

def _mock_role2_dedup_call(summary: str, candidates: List[Dict]) -> Dict[str, float]:
    """
    Fallback mock for Role 2's MiniLM deduplication API.
    Used if Role 2 is offline during the demo loop.
    Returns mapping of incident_id -> semantic similarity score (0-1).
    """
    scores = {}
    words1 = set(summary.lower().split())
    for cand in candidates:
        words2 = set(cand["summary"].lower().split())
        if not words1 or not words2:
            scores[cand["incident_id"]] = 0.0
            continue
        overlap = len(words1.intersection(words2))
        scores[cand["incident_id"]] = overlap / max(len(words1), len(words2))
    return scores

def perform_link_incident(lat: Optional[float], lon: Optional[float], summary: str, reported_time: str) -> Tuple[Optional[str], float, str]:
    """
    R3-3: Combined Geo + Semantic Incident Linking.
    Weighting: 0.4 geo + 0.6 semantic. Map threshold >= 0.65.
    Returns (incident_id, confidence, reason).
    """
    candidates = []
    
    with get_db() as db:
        if lat is not None and lon is not None:
            # Stage 1: Geo + Time Filter
            candidates = get_nearby_incidents_logic(lat, lon, radius_m=500, within_minutes=30)
        else:
            # Stage 1: Geo skipped. Fetch all from last 30 mins.
            try:
                rep_time = datetime.datetime.fromisoformat(reported_time.replace("Z", "+00:00"))
            except ValueError:
                rep_time = datetime.datetime.utcnow()
                
            cutoff = rep_time - datetime.timedelta(minutes=30)
            recent = db.query(Incident).filter(Incident.updated_at >= cutoff).all()
            for inc in recent:
                candidates.append({
                    "incident_id": inc.id,
                    "distance_m": 0.0, # N/A if no lat/lon provided
                    "summary": inc.summary
                })

    if not candidates:
        return None, 0.0, "No matching incident found"

    # Stage 2: Attempt HTTP call to Role 2 (AI Service :8001 /dedup)
    semantic_scores = {}
    try:
        cand_payload = [{"incident_id": c["incident_id"], "summary": c["summary"]} for c in candidates]
        resp = requests.post("http://localhost:8001/dedup", json={"summary": summary, "candidates": cand_payload}, timeout=2.0)
        if resp.status_code == 200:
            # Assume role 2 returns scores mapped by ID
            # Let's write a generic reader. If it just returns best match, we can adapt.
            # R3 requirement just says we "pass them to Role 2's /dedup endpoint to get semantic similarity scores"
            data = resp.json()
            semantic_scores = data.get("scores", {}) 
        else:
            raise Exception("Role 2 dedup failed")
    except Exception:
        # Fallback to Mock MiniLM Keyword similarity if AI service isn't started yet
        semantic_scores = _mock_role2_dedup_call(summary, candidates)

    best_cand_id = None
    best_combined = 0.0
    best_reason = "No matching incident found"

    for cand in candidates:
        inc_id = cand["incident_id"]
        sem_score = semantic_scores.get(inc_id, 0.0)
        
        # geo_score = 1 - (distance_m / 500) clamped to [0,1]
        dist = cand["distance_m"]
        geo_score = max(0.0, min(1.0, 1.0 - (dist / 500.0)))
        
        # Combined score calculation!
        if lat is not None and lon is not None:
            combined = (0.4 * geo_score) + (0.6 * sem_score)
            reason = f"Geo proximity {dist:.0f} m + semantic similarity {sem_score:.2f} → combined {combined:.2f}"
        else:
            # If no coordinates, we only judge by semantic score
            combined = sem_score
            reason = f"No geo coordinates provided + semantic similarity {sem_score:.2f} → combined {combined:.2f}"
            
        if combined > best_combined:
            best_combined = combined
            best_cand_id = inc_id
            best_reason = reason

    if best_combined >= 0.65:
        return best_cand_id, best_combined, best_reason
    else:
        return None, best_combined, "No matching incident found"
