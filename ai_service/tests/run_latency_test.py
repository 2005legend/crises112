"""
End-to-end latency test for the AI service.
Measures p50 and p95 latency for text modality against a running service.

Prerequisites: uvicorn ai_service.main:app --port 8001 must be running.

Run: python ai_service/tests/run_latency_test.py
"""
import os
import sys
import time
import statistics

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

BASE_URL = "http://localhost:8001"

TEST_REPORTS = [
    "Lorry hit bike near Anna Nagar signal, one person injured and bleeding on road",
    "Building mein aag lagi hai T Nagar main road pe, bahut dhuan aa raha hai",
    "Old man collapsed near Silk Board junction, not breathing, no pulse",
    "Multiple vehicles crashed on NH-48 near Electronic City, highway blocked",
    "Anna Nagar signal-la oru accident aagiruku, oru payyan kizhe vizhundhan",
    "Flood water entered houses in Velachery, families stranded on rooftops",
    "Armed robbery at petrol bunk on OMR, man with knife threatening staff",
    "Child fell into open manhole near T Nagar bus stand, rescue needed",
]


def check_health():
    try:
        resp = requests.get(f"{BASE_URL}/ai/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def measure_text_latency(text: str) -> tuple[float, dict]:
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/ai/fuse-report",
        data={"modality": "text", "text": text},
        timeout=30,
    )
    elapsed_ms = (time.time() - start) * 1000
    return elapsed_ms, resp.json()


def run():
    print("Checking service health...")
    if not check_health():
        print(f"\n  ✗ Service not running at {BASE_URL}")
        print("  Start it with: uvicorn ai_service.main:app --port 8001 --reload")
        sys.exit(1)
    print("  ✓ Service is up\n")

    latencies = []
    errors = []

    print(f"Running {len(TEST_REPORTS)} text requests...\n")

    for i, text in enumerate(TEST_REPORTS, 1):
        try:
            ms, result = measure_text_latency(text)
            latencies.append(ms)
            has_errors = len(result.get("errors", [])) > 0
            incident_type = (result.get("extracted") or {}).get("incident_type", "null")
            status = "✓" if not has_errors else "⚠"
            print(f"  {status} [{i:2}] {ms:6.0f}ms  type={incident_type:<15}  "
                  f"errors={result.get('errors', [])}")
        except Exception as e:
            errors.append(str(e))
            print(f"  ✗ [{i:2}] FAILED: {e}")

    if not latencies:
        print("\nNo successful requests — check service logs")
        return

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies)
    avg = statistics.mean(latencies)
    min_l = min(latencies)
    max_l = max(latencies)

    print(f"\n{'='*55}")
    print(f"  LATENCY RESULTS ({len(latencies)} successful requests)")
    print(f"  Min  : {min_l:.0f}ms")
    print(f"  Avg  : {avg:.0f}ms")
    print(f"  P50  : {p50:.0f}ms")
    print(f"  P95  : {p95:.0f}ms")
    print(f"  Max  : {max_l:.0f}ms")
    print(f"{'='*55}")

    target_ms = 3000
    if p50 <= target_ms:
        print(f"\n  ✓ P50 {p50:.0f}ms is under the {target_ms}ms target for text modality")
    else:
        print(f"\n  ✗ P50 {p50:.0f}ms exceeds the {target_ms}ms target — check Groq latency")

    if errors:
        print(f"\n  {len(errors)} request(s) failed: {errors}")


if __name__ == "__main__":
    run()
