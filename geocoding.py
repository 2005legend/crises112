import time
import string
from typing import Optional, Tuple
from geopy.geocoders import Nominatim, ArcGIS
from geopy.exc import GeocoderTimedOut
from models import get_db, GeocodeCache, ReverseGeocodeCache

geolocator = Nominatim(user_agent="eifs_geo_service_role3")
# If you successfully set up a local Nominatim server from the github repo, you can point geopy to it like this:
# geolocator = Nominatim(domain="localhost:8080", scheme="http", user_agent="eifs_geo_service")

LAST_CALL_TIME = 0

def _rate_limit():
    global LAST_CALL_TIME
    now = time.time()
    elapsed = now - LAST_CALL_TIME
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    LAST_CALL_TIME = time.time()

def normalize_text(text: str) -> str:
    """Lowercase and strip punctuation for caching keys (R3-1.5)"""
    if not text:
        return ""
    text = text.lower()
    return text.translate(str.maketrans('', '', string.punctuation)).strip()

def extract_landmarks(lat: float, lon: float) -> str:
    """Hits reverse geocoding to pull explicit physical landmarks like hospitals or malls nearby."""
    _rate_limit()
    try:
        # Nominatim zoom=17 focuses strictly on buildings/amenities instead of broad towns
        rev = geolocator.reverse((lat, lon), zoom=17, timeout=2.5)
        if rev and rev.raw.get("address"):
            addr = rev.raw["address"]
            landmarks = []
            keys = ["amenity", "building", "historic", "tourism", "shop", "leisure", "railway", "highway", "man_made"]
            for k in keys:
                if k in addr:
                    landmarks.append(addr[k].title())
            if landmarks:
                return ", ".join(list(set(landmarks)))
    except Exception:
        pass
    return "No obvious distinct landmark"

def geocode_location(location_text: str, city_hint: Optional[str] = None, state_hint: Optional[str] = None) -> Tuple[Optional[float], Optional[float], float, Optional[str], Optional[str]]:
    """
    R3-1: Geocode endpoint logic. Returns (lat, lon, confidence, resolved_name, landmarks).
    """
    if not location_text:
        return None, None, 0.0, None, None
        
    normalized_query = normalize_text(location_text)
    
    with get_db() as db:
        cached = db.query(GeocodeCache).filter(GeocodeCache.query == normalized_query).first()
        if cached:
            return cached.lat, cached.lon, 1.0 if cached.lat else 0.0, cached.resolved_name, cached.landmarks
            
        _rate_limit()
        
        # Build search dict to help Nominatim be more precise
        query_dict = {"street": location_text}
        if city_hint: query_dict["city"] = city_hint
        if state_hint: query_dict["state"] = state_hint
        # Fallback to string search if dict fails or just use string
        search_str = location_text
        if city_hint: search_str += f", {city_hint}"
        if state_hint: search_str += f", {state_hint}"

        try:
            # ENHANCED ACCURACY: Force Nominatim to ONLY search within India ("in") 
            # and strictly limit the response to the best match. This drastically improves precision!
            location = geolocator.geocode(
                search_str, 
                country_codes="in", 
                limit=1,
                timeout=2.5
            )
            
            if location:
                lat, lon = location.latitude, location.longitude
                resolved_name = location.address
                conf = 0.9
                landmarks = extract_landmarks(lat, lon)
            else:
                # Fallback to ArcGIS for fussy/messy Indian addresses that OSM misses
                # ArcGIS is incredibly robust and free for basic geocoding in geopy
                print(f"Nominatim missed '{search_str}'. Falling back to ArcGIS...")
                arcgis = ArcGIS(user_agent="eifs_geo_service_role3_fallback")
                try:
                    arc_location = arcgis.geocode(search_str, timeout=2.5)
                except Exception:
                    arc_location = None
                    
                if arc_location:
                    lat, lon = arc_location.latitude, arc_location.longitude
                    resolved_name = arc_location.address
                    conf = 0.8
                    landmarks = extract_landmarks(lat, lon)
                else:
                    print(f"ERROR: Extremely unrecognized location '{search_str}'. Failing cleanly.")
                    new_cache = GeocodeCache(query=normalized_query, lat=None, lon=None, resolved_name=None, landmarks=None)
                    db.add(new_cache)
                    db.commit()
                    return None, None, 0.0, None, None

            new_cache = GeocodeCache(query=normalized_query, lat=lat, lon=lon, resolved_name=resolved_name, landmarks=landmarks)
            db.add(new_cache)
            db.commit()
            return lat, lon, conf, resolved_name, landmarks
                
        except GeocoderTimedOut:
            return None, None, 0.0, None, None


def reverse_geocode(lat: float, lon: float) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    R3-5: Reverse geocoding. Caches at ~100m precision (3 decimal places).
    Returns (area_name, district, city).
    """
    lat_r = round(lat, 3)
    lon_r = round(lon, 3)
    
    with get_db() as db:
        cached = db.query(ReverseGeocodeCache).filter(
            ReverseGeocodeCache.lat_rounded == lat_r,
            ReverseGeocodeCache.lon_rounded == lon_r
        ).first()
        if cached:
            return cached.area_name, cached.district, cached.city
            
        _rate_limit()
        try:
            rev_loc = geolocator.reverse((lat, lon), exactly_one=True, timeout=2.5)
            area_name = None
            district = None
            city = None
            
            if rev_loc and rev_loc.raw.get("address"):
                addr = rev_loc.raw["address"]
                # Grab most specific administrative name
                area_name = addr.get("suburb", addr.get("neighbourhood", addr.get("village", None)))
                district = addr.get("city_district", addr.get("county", None))
                city = addr.get("city", addr.get("town", None))
                
            new_cache = ReverseGeocodeCache(
                lat_rounded=lat_r, 
                lon_rounded=lon_r, 
                area_name=area_name, 
                district=district, 
                city=city
            )
            db.add(new_cache)
            db.commit()
            return area_name, district, city
            
        except GeocoderTimedOut:
            return None, None, None
