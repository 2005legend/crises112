# scripts/simulate_reports.py
import time
import requests
import random

API_URL = "http://localhost:8000/reports"

SAMPLE_REPORTS = [
    {"text": "Accident near Anna Nagar, 2 injured", "source": "text"},
    {"text": "Bike crash at Anna Nagar signal", "source": "text"},
    {"text": "Fire breakout in T Nagar building", "source": "text"},
    {"text": "Smoke seen near Velachery market", "source": "text"},
    {"text": "Bus accident on OMR, multiple injured", "source": "text"},
    {"text": "Heavy crowd near Central station", "source": "text"},
]

def simulate():
    print("Starting simulation...\n")

    while True:
        report = random.choice(SAMPLE_REPORTS)

        try:
            res = requests.post(API_URL, json=report)
            print(f"Sent: {report['text']}")
            print(f"Response: {res.json()}\n")
        except Exception as e:
            print("Error:", e)

        # simulate real-time delay
        time.sleep(random.randint(2, 5))


if __name__ == "__main__":
    simulate()