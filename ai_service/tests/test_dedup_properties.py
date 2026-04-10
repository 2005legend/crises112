# Feature: emergency-intelligence-fusion, Property 4: Dedup Threshold Correctness
# Feature: emergency-intelligence-fusion, Property 5: New Incident Created on No Match
"""
Property-based tests for the Dedup Engine.
Uses the real MiniLM model for embedding computation.
"""
import pytest
from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st
from engines.dedup import find_match, cosine_similarity, get_embedding, SIMILARITY_THRESHOLD


# ---------------------------------------------------------------------------
# Property 4: Dedup Threshold Correctness
# Validates: Requirements 4.2, 4.3, R2-4.2, R2-4.3, R2-4.4
# ---------------------------------------------------------------------------

@given(
    st.text(min_size=5, max_size=200, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
    st.text(min_size=5, max_size=200, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_dedup_threshold_correctness(text_a, text_b):
    """
    For any pair of summaries, find_match must return match=incident_id iff
    cosine similarity > 0.75, and match=null otherwise.
    Similarity exactly 0.75 must NOT trigger a merge.
    **Validates: Requirements 4.2, 4.3, R2-4.2, R2-4.3, R2-4.4**
    """
    assume(text_a.strip() and text_b.strip())

    emb_a = get_embedding(text_a)
    emb_b = get_embedding(text_b)
    actual_similarity = cosine_similarity(emb_a, emb_b)

    result = find_match(text_a, [{"incident_id": "test-001", "summary": text_b}])

    if actual_similarity > SIMILARITY_THRESHOLD:
        assert result["match"] == "test-001", (
            f"Expected match for similarity {actual_similarity:.4f} > {SIMILARITY_THRESHOLD}, "
            f"but got match=None"
        )
    else:
        assert result["match"] is None, (
            f"Expected no match for similarity {actual_similarity:.4f} <= {SIMILARITY_THRESHOLD}, "
            f"but got match={result['match']}"
        )


def test_dedup_boundary_exactly_075():
    """
    Similarity exactly equal to 0.75 must NOT trigger a merge (strict > threshold).
    **Validates: R2-4.3, R2-4.4**
    """
    import numpy as np
    from unittest.mock import patch

    # Create two unit vectors with cosine similarity exactly 0.75
    a = np.array([1.0, 0.0, 0.0])
    b = np.array([0.75, np.sqrt(1 - 0.75**2), 0.0])

    with patch("engines.dedup.get_embedding") as mock_emb:
        mock_emb.side_effect = [a, b]
        result = find_match("text_a", [{"incident_id": "test-001", "summary": "text_b"}])

    assert result["match"] is None, (
        f"Similarity exactly 0.75 should NOT trigger a merge, but got match={result['match']}"
    )


# ---------------------------------------------------------------------------
# Property 5: New Incident Created on No Match
# Validates: Requirements 4.3, R2-4.4
# ---------------------------------------------------------------------------

@st.composite
def low_similarity_candidates(draw):
    """
    Generate a summary and a list of candidate summaries where all similarities
    are expected to be <= 0.75 (semantically unrelated texts).
    """
    # Use clearly unrelated topics to ensure low similarity
    topics_a = ["fire truck engine", "ambulance hospital medical", "police station crime"]
    topics_b = ["cooking recipe pasta", "football match score", "weather forecast rain", "music concert band"]

    summary = draw(st.sampled_from(topics_a))
    num_candidates = draw(st.integers(min_value=1, max_value=5))
    candidates = [
        {"incident_id": f"cand-{i}", "summary": draw(st.sampled_from(topics_b))}
        for i in range(num_candidates)
    ]
    return summary, candidates


@given(low_similarity_candidates())
@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
def test_no_match_returns_null(summary_and_candidates):
    """
    For any report whose best similarity score <= 0.75 against all candidates,
    find_match must return match=null.
    **Validates: Requirements 4.3, R2-4.4**
    """
    summary, candidates = summary_and_candidates

    # Compute actual similarities to verify the assumption
    query_emb = get_embedding(summary)
    all_low = True
    for cand in candidates:
        cand_emb = get_embedding(cand["summary"])
        sim = cosine_similarity(query_emb, cand_emb)
        if sim > SIMILARITY_THRESHOLD:
            all_low = False
            break

    if not all_low:
        # Skip this example — the generated texts happened to be similar
        return

    result = find_match(summary, candidates)
    assert result["match"] is None, (
        f"Expected match=null when all similarities <= {SIMILARITY_THRESHOLD}, "
        f"but got match={result['match']} with score={result['similarity_score']}"
    )


def test_empty_candidates_returns_null():
    """find_match with empty candidates list must return match=null."""
    result = find_match("some emergency summary", [])
    assert result["match"] is None
    assert result["similarity_score"] == 0.0
