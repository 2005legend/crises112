# integrations/geo_service.py

import requests
from config import GEO_SERVICE_URL

def call_geo_service(data: dict) -> dict:
    """
    Sends structured AI output to geo/dedup service
    Returns incident assignment
    """

    try:
        response = requests.post(GEO_SERVICE_URL, json=data, timeout=10)

        if response.status_code != 200:
            raise Exception(f"GEO service error: {response.status_code}")

        result = response.json()

        # Expected:
        # { "incident_id": "123" } OR { "incident_id": None }

        if "incident_id" not in result:
            raise Exception("Invalid geo response")

        return result

    except Exception as e:
        print("GEO SERVICE FAILURE:", str(e))
        return {"incident_id": None}