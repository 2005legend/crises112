"""
Run the 18-pair dedup test dataset against the real MiniLM model.
Prints precision, recall, F1, and per-pair results.

Run: python ai_service/tests/run_batch_dedup_test.py
"""
import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sentence_transformers import SentenceTransformer
from ai_service.engines.dedup_engine import DedupEngine

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dedup_test_dataset.json")


def run():
    print("Loading all-MiniLM-L6-v2...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    engine = DedupEngine(model)

    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    pairs = dataset["pairs"]
    tp = fp = fn = tn = 0
    results = []

    print(f"\nRunning {len(pairs)} pairs...\n")

    for pair in pairs:
        # For same_event pairs: simulate geo proximity (reports about same event are nearby)
        # For different pairs: simulate no geo data (neutral)
        # This mirrors real usage where geo service provides distance_m
        distance_m = 80.0 if pair["expected_merge"] else None

        result = engine.find_match(
            summary=pair["report_summary"],
            candidates=[{
                "incident_id": "test-inc",
                "summary": pair["incident_summary"],
                "distance_m": distance_m,
            }],
        )
        predicted = result["match"] is not None
        expected = pair["expected_merge"]
        correct = predicted == expected

        if expected and predicted:     tp += 1
        elif not expected and predicted: fp += 1
        elif expected and not predicted: fn += 1
        else:                            tn += 1

        status = "PASS" if correct else "FAIL"
        results.append({
            "id": pair["id"],
            "category": pair["category"],
            "expected": "merge" if expected else "no_merge",
            "predicted": "merge" if predicted else "no_merge",
            "combined_score": result["combined_score"],
            "threshold": result["threshold_used"],
            "correct": correct,
        })

        print(f"  {status} [{pair['id']:6}] {pair['category']:<35} "
              f"score={result['combined_score']:.3f} threshold={result['threshold_used']:.2f} "
              f"-> {'MERGE' if predicted else 'NO_MERGE'} (expected {'MERGE' if expected else 'NO_MERGE'})")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy  = (tp + tn) / len(pairs)

    print(f"\n{'='*65}")
    print(f"  RESULTS: {len(pairs)} pairs")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision : {precision:.3f}")
    print(f"  Recall    : {recall:.3f}")
    print(f"  F1 Score  : {f1:.3f}")
    print(f"  Accuracy  : {accuracy:.3f}")
    print(f"{'='*65}")

    if f1 >= 0.90:
        print(f"\n  PASS F1 {f1:.2f} meets the >=0.90 target")
    else:
        print(f"\n  FAIL F1 {f1:.2f} is below the 0.90 target -- review failing pairs above")

    # Show failures
    failures = [r for r in results if not r["correct"]]
    if failures:
        print(f"\n  Failing pairs ({len(failures)}):")
        for f in failures:
            print(f"    [{f['id']}] expected={f['expected']} predicted={f['predicted']} score={f['combined_score']:.3f}")


if __name__ == "__main__":
    run()
