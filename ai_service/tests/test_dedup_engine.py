"""
Tests for the Dedup Engine.
Covers: threshold correctness, cache behaviour, batch test accuracy, edge cases.
Includes property-based tests (Properties 4, 5) using hypothesis.
"""
import json
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, assume, strategies as st

from ai_service.engines.dedup_engine import (
    DedupEngine,
    cosine_similarity,
    normalize_text,
    text_hash,
    get_threshold,
    MERGE_THRESHOLDS,
    keyword_overlap,
    geo_score,
    temporal_score,
    entity_boost,
)

SIMILARITY_THRESHOLD = MERGE_THRESHOLDS["default"]  # 0.65 — used in property tests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mock_model(similarity_value: float):
    """
    Create a mock SentenceTransformer that returns vectors whose cosine similarity
    equals the given value when compared to each other.
    """
    model = MagicMock()
    # Two orthogonal-ish vectors whose cosine sim we can control
    vec_a = np.array([1.0, 0.0, 0.0])
    vec_b = np.array([similarity_value, np.sqrt(max(0, 1 - similarity_value**2)), 0.0])
    call_count = [0]

    def encode_side_effect(text, convert_to_numpy=True):
        call_count[0] += 1
        return vec_a if call_count[0] % 2 == 1 else vec_b

    model.encode.side_effect = encode_side_effect
    return model


def make_real_model():
    """Load the actual MiniLM model for integration-style tests."""
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Unit tests — cosine similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = np.array([1.0, 2.0, 3.0])
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self):
        v = np.array([1.0, 0.0])
        assert abs(cosine_similarity(v, -v) - (-1.0)) < 1e-6

    def test_zero_vector_returns_zero(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 2.0])
        assert cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# Unit tests — normalize and hash
# ---------------------------------------------------------------------------

class TestNormalizeAndHash:
    def test_normalize_lowercases(self):
        assert normalize_text("FIRE Near Anna Nagar") == "fire near anna nagar"

    def test_normalize_strips_punctuation(self):
        assert normalize_text("fire, near anna-nagar!") == "fire near annanagar"

    def test_same_text_same_hash(self):
        assert text_hash("fire near anna nagar") == text_hash("fire near anna nagar")

    def test_different_text_different_hash(self):
        assert text_hash("fire near anna nagar") != text_hash("flood in velachery")


# ---------------------------------------------------------------------------
# Unit tests — DedupEngine
# ---------------------------------------------------------------------------

class TestDedupEngine:
    def test_no_candidates_returns_null_match(self):
        model = MagicMock()
        engine = DedupEngine(model)
        result = engine.find_match("some summary", [])
        assert result["match"] is None
        assert result["similarity_score"] == 0.0

    def test_above_threshold_returns_match(self):
        """High semantic + close geo should exceed threshold."""
        model = make_mock_model(0.99)
        engine = DedupEngine(model)
        result = engine.find_match(
            summary="lorry hit bike near Anna Nagar",
            candidates=[{
                "incident_id": "inc-001",
                "summary": "truck motorcycle collision Anna Nagar",
                "distance_m": 50,  # very close → geo score ~0.78
            }],
        )
        assert result["match"] == "inc-001"

    def test_below_threshold_returns_null(self):
        model = make_mock_model(0.3)
        engine = DedupEngine(model)
        result = engine.find_match(
            summary="flood in velachery",
            candidates=[{"incident_id": "inc-002", "summary": "robbery on MG Road"}],
        )
        assert result["match"] is None

    def test_exactly_at_threshold_no_merge(self):
        """Combined score exactly at threshold must NOT trigger a merge (strict >)."""
        model = make_mock_model(SIMILARITY_THRESHOLD)
        engine = DedupEngine(model)
        result = engine.find_match(
            summary="some text",
            candidates=[{"incident_id": "inc-003", "summary": "some other text"}],
        )
        assert result["match"] is None

    def test_merge_reason_contains_incident_id(self):
        model = make_mock_model(0.95)
        engine = DedupEngine(model)
        result = engine.find_match(
            summary="fire near MG Road",
            candidates=[{"incident_id": "inc-007", "summary": "building fire MG Road"}],
        )
        if result["match"]:
            assert "inc-007" in result["merge_reason"]

    def test_embedding_cache_hit_skips_reencoding(self):
        model = MagicMock()
        model.encode.return_value = np.array([1.0, 0.0, 0.0])
        engine = DedupEngine(model)
        text = "fire near anna nagar signal"
        engine._encode(text)
        engine._encode(text)
        assert model.encode.call_count == 1

    def test_signal_breakdown_present_in_response(self):
        model = make_mock_model(0.9)
        engine = DedupEngine(model)
        result = engine.find_match(
            summary="accident near signal",
            candidates=[{"incident_id": "inc-010", "summary": "crash at junction"}],
        )
        assert "signal_breakdown" in result
        assert "semantic" in result["signal_breakdown"]

    def test_geo_score_boosts_nearby_candidate(self):
        """Candidate with distance_m=50 should score higher than one at 450m."""
        model = MagicMock()
        model.encode.return_value = np.array([1.0, 0.0, 0.0])
        engine = DedupEngine(model)
        result = engine.find_match(
            summary="accident",
            candidates=[
                {"incident_id": "near", "summary": "accident", "distance_m": 50},
                {"incident_id": "far",  "summary": "accident", "distance_m": 450},
            ],
        )
        # Both have same semantic score; near one should win
        assert result["match"] == "near"

    def test_dynamic_threshold_fire_lower(self):
        assert get_threshold("fire") < get_threshold("violence")

    def test_dynamic_threshold_violence_higher(self):
        assert get_threshold("violence") > get_threshold("road_accident")

    def test_keyword_overlap_same_keywords(self):
        score = keyword_overlap("fire injured near junction", "fire accident injured")
        assert score > 0.3

    def test_keyword_overlap_no_keywords(self):
        score = keyword_overlap("hello world", "foo bar")
        assert score == 0.5  # neutral

    def test_geo_score_zero_distance(self):
        assert abs(geo_score(0) - 1.0) < 0.01

    def test_geo_score_far_distance(self):
        assert geo_score(1000) < 0.01

    def test_entity_boost_shared_location(self):
        boost = entity_boost("Anna Nagar signal", "near Anna Nagar junction")
        assert boost > 0.0

    def test_entity_boost_no_shared(self):
        boost = entity_boost("Anna Nagar", "T Nagar")
        assert boost == 0.0


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Property 4: Dedup Threshold Correctness
@given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@settings(max_examples=100)
def test_property4_dedup_threshold_correctness(sim_value):
    """
    For any semantic similarity value, the combined score (with neutral geo/keyword/temporal)
    should result in a match iff combined > threshold.
    """
    model = make_mock_model(sim_value)
    engine = DedupEngine(model)
    result = engine.find_match(
        summary="test summary",
        candidates=[{"incident_id": "inc-test", "summary": "candidate summary"}],
    )
    threshold = result["threshold_used"]
    combined = result["combined_score"]
    if combined > threshold:
        assert result["match"] == "inc-test"
    else:
        assert result["match"] is None


@given(st.floats(min_value=0.0, max_value=0.3, allow_nan=False))
@settings(max_examples=100)
def test_property5_no_match_signals_new_incident(sim_value):
    """
    When semantic similarity is very low, combined score stays below threshold
    and match is null — signalling a new incident should be created.
    """
    model = make_mock_model(sim_value)
    engine = DedupEngine(model)
    result = engine.find_match(
        summary="completely different emergency",
        candidates=[{"incident_id": "inc-existing", "summary": "unrelated incident"}],
    )
    assert result["match"] is None


# ---------------------------------------------------------------------------
# Dataset accuracy test
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_dedup_dataset_accuracy():
    """
    Run the full dedup test dataset and assert ≥ 90% accuracy on both
    same-event merges and different-event separations.
    Requires the real MiniLM model — skipped if not available.
    """
    model = make_real_model()
    if model is None:
        pytest.skip("MiniLM model not available")

    with open("ai_service/tests/dedup_test_dataset.json") as f:
        dataset = json.load(f)

    engine = DedupEngine(model)
    tp = fp = fn = tn = 0

    for pair in dataset["pairs"]:
        result = engine.find_match(
            summary=pair["report_summary"],
            candidates=[{"incident_id": "test-inc", "summary": pair["incident_summary"]}],
        )
        predicted = result["match"] is not None
        expected = pair["expected_merge"]

        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif expected and not predicted:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    accuracy = (tp + tn) / len(dataset["pairs"])

    print(f"\nDedup dataset results: precision={precision:.2f}, recall={recall:.2f}, accuracy={accuracy:.2f}")
    assert recall >= 0.90, f"Recall {recall:.2f} below 90% — too many missed merges"
    assert precision >= 0.90, f"Precision {precision:.2f} below 90% — too many false merges"
