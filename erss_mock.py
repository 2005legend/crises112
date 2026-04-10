import argparse
import json
import time
import requests

# R3-6: ERSS Mock Integration
# Simulates reports arriving from 112 Command Room

def emit_scenario(file_path: str, speed_multiplier: float):
    print(f"--- Firing ERSS Mock (Scenario: {file_path}) ---")
    
    try:
        with open(file_path, 'r') as f:
            reports = json.load(f)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return

    # Backend API is on :8000
    BACKEND_URL = "http://localhost:8000/reports"

    print("Checking Backend (Role 1)...")
    try:
        # Check health endpoint if possible, or just fail cleanly on first post
        requests.get("http://localhost:8000/health", timeout=2)
    except:
        print("WARNING: Could not reach http://localhost:8000. Is Role 1 running?")
    
    for idx, report in enumerate(reports):
        # Format logs as requested: Report #X | Modality: <type> | Text: <trunc>
        modality = report.get("modality", "text")
        raw_text = report.get("raw_text", "")
        trunc_text = (raw_text[:40] + '...') if len(raw_text) > 40 else raw_text
        
        # Build multipart/form-data equivalent if needed, or stick to json if Backend supports testing
        # The spec indicates "multipart/form-data".
        
        payload = {
            "modality": modality,
            "raw_text": raw_text,
            "source": report.get("source", "9841XXXXXX")
        }
        
        try:
            # We send as multipart/form-data as Backend expects it
            resp = requests.post(BACKEND_URL, data=payload)
            status = resp.status_code
        except Exception as e:
            status = f"FAILED ({e})"
            
        print(f"Report #{idx+1:02} | Modality: {modality:5} | Text: {trunc_text:43} | Status: HTTP {status}")
        
        # Default delay is 2 seconds, multiplied by speed flag
        time.sleep(2.0 * speed_multiplier)

    print("--- Simulation Complete ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ERSS Command Room Simulator")
    parser.add_argument("--file", type=str, required=True, help="Path to scenario JSON file")
    parser.add_argument("--speed", type=float, default=1.0, help="Delay multiplier. 0.5 = twice as fast")
    
    args = parser.parse_args()
    emit_scenario(args.file, args.speed)
