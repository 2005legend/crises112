import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import requests

data = [
    {"text": "Accident in Anna Nagar", "source": "text"},
    {"text": "Bike crash Anna Nagar signal", "source": "text"}
]

for d in data:
    # Note: The endpoint expects form data, but for simplicity, we'll assume JSON for now
    # In production, use proper form encoding
    response = requests.post("http://localhost:8000/reports", json=d)
    print(response.status_code, response.text)