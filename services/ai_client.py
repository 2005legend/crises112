import requests
from config import AI_SERVICE_URL

def call_ai(payload):
    res = requests.post(AI_SERVICE_URL, json=payload)
    return res.json()