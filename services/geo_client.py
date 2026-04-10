import requests
from config import GEO_SERVICE_URL

def assign_incident(data):
    res = requests.post(GEO_SERVICE_URL, json=data)
    return res.json()  # {incident_id: ...} or None