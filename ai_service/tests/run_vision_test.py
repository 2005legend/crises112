"""
Manual image test for NVIDIA NIM vision engine.
Run: python ai_service/tests/run_vision_test.py
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_service.engines.vision_engine import VisionEngine

IMAGES = [
    r"C:\Users\sidaa\Crises112\test image 1.jpg",
    r"C:\Users\sidaa\Crises112\test image 2.jpg",
]


async def main():
    engine = VisionEngine()
    for path in IMAGES:
        name = os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()

        print(f"\n{'='*65}")
        print(f"  IMAGE : {name}  ({len(data)//1024} KB)")
        print(f"{'='*65}")

        result = await engine.caption(data)

        # Print key fields clearly
        print(f"  Scene Type       : {result.get('scene_type')}")
        print(f"  Incident Category: {result.get('incident_category')}")
        print(f"  Severity Score   : {result.get('severity_score')}  →  {result.get('severity_label')}")
        print(f"  Confidence       : {result.get('confidence')}")
        print(f"  Responders On Scene: {result.get('responders_present')}")
        print(f"\n  Summary: {result.get('actionable_summary')}")

        print(f"\n  Severity Audit:")
        for row in result.get("severity_audit", []):
            print(f"    +{row['weight']:>3}  {row['factor']:<25} — {row['explanation']}")

        victims = result.get("victims", {})
        print(f"\n  Victims:")
        for k, v in victims.items():
            print(f"    {k}: {v}")

        hazards = result.get("hazards", {})
        active_hazards = [k for k, v in hazards.items() if v]
        print(f"\n  Active Hazards   : {active_hazards if active_hazards else 'none'}")

        env = result.get("environment", {})
        print(f"\n  Environment:")
        print(f"    location_type : {env.get('location_type')}")
        print(f"    urban_rural   : {env.get('urban_rural')}")
        print(f"    landmark      : {env.get('landmark_visible')}")

        vehicles = result.get("vehicles", {})
        print(f"\n  Vehicles: {vehicles.get('types_present')}  count={vehicles.get('count')}")
        print(f"    overturned={vehicles.get('overturned')}  on_fire={vehicles.get('on_fire')}  blocking={vehicles.get('blocking_road')}")

        print(f"\n  Full JSON:")
        print(json.dumps(result, indent=4))


if __name__ == "__main__":
    asyncio.run(main())
