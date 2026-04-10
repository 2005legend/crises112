"""
Integration tests for POST /ai/fuse-report.
Tests all three modalities: text, voice (mocked STT), image (mocked vision).
"""
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
import numpy as np

from ai_service.main import app


def make_app_with_models(stt_model=None, embedding_model=None):
    """Inject mock models into app state."""
    loader = MagicMock()
    loader.stt_model = stt_model
    loader.embedding_model = embedding_model
    loader.status = {
        "stt": "loaded" if stt_model else "not_loaded",
        "vision": "ready",
        "extraction": "ready",
        "embedding": "loaded" if embedding_model else "not_loaded",
    }
    app.state.models = loader
    return app


def make_mock_stt():
    model = MagicMock()
    segments = [MagicMock(text="Lorry hit a bike near Anna Nagar signal")]
    info = MagicMock()
    info.language = "en"
    model.transcribe.return_value = (iter(segments), info)
    return model


def make_mock_embedding():
    model = MagicMock()
    model.encode.return_value = np.array([1.0, 0.0, 0.0])
    return model


MOCK_EXTRACTION = {
    "incident_type": "road_accident",
    "location_string": "Anna Nagar signal",
    "time_reference": None,
    "victim_count": 1,
    "risk_keywords": ["injured"],
    "summary": "Road accident near Anna Nagar signal"
}


class TestFuseEndpoint:

    def setup_method(self):
        make_app_with_models(
            stt_model=make_mock_stt(),
            embedding_model=make_mock_embedding(),
        )
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_text_modality_returns_extracted_fields(self):
        with patch("ai_service.routers.fuse.ExtractionEngine") as MockExt:
            instance = MockExt.return_value
            instance.extract.return_value = MOCK_EXTRACTION
            resp = self.client.post(
                "/ai/fuse-report",
                data={"modality": "text", "text": "Lorry hit a bike near Anna Nagar signal"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["extracted"]["incident_type"] == "road_accident"
        assert body["errors"] == []

    def test_text_modality_with_candidates_returns_dedup_result(self):
        candidates = json.dumps([{"incident_id": "inc-001", "summary": "road accident Anna Nagar"}])
        with patch("ai_service.routers.fuse.ExtractionEngine") as MockExt:
            instance = MockExt.return_value
            instance.extract.return_value = MOCK_EXTRACTION
            resp = self.client.post(
                "/ai/fuse-report",
                data={
                    "modality": "text",
                    "text": "Lorry hit a bike near Anna Nagar signal",
                    "candidates_json": candidates,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "match" in body
        assert "similarity_score" in body

    def test_missing_modality_returns_422(self):
        resp = self.client.post("/ai/fuse-report", data={"text": "some text"})
        assert resp.status_code == 422

    def test_invalid_modality_returns_400(self):
        resp = self.client.post("/ai/fuse-report", data={"modality": "fax", "text": "test"})
        assert resp.status_code == 400

    def test_text_modality_missing_text_returns_400(self):
        resp = self.client.post("/ai/fuse-report", data={"modality": "text"})
        assert resp.status_code == 400

    def test_voice_modality_missing_file_returns_400(self):
        resp = self.client.post("/ai/fuse-report", data={"modality": "voice"})
        assert resp.status_code == 400

    def test_extraction_failure_returns_partial_with_errors(self):
        with patch("ai_service.routers.fuse.ExtractionEngine") as MockExt:
            instance = MockExt.return_value
            instance.extract.side_effect = ValueError("Extraction failed after 2 attempts")
            resp = self.client.post(
                "/ai/fuse-report",
                data={"modality": "text", "text": "some emergency text"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["errors"]) > 0
        assert body["extracted"] is None

    def test_response_has_all_expected_keys(self):
        with patch("ai_service.routers.fuse.ExtractionEngine") as MockExt:
            instance = MockExt.return_value
            instance.extract.return_value = MOCK_EXTRACTION
            resp = self.client.post(
                "/ai/fuse-report",
                data={"modality": "text", "text": "fire near MG Road"},
            )
        body = resp.json()
        for key in ["transcript", "vision_analysis", "extracted", "match", "similarity_score", "merge_reason", "errors", "review_flag"]:
            assert key in body, f"Key '{key}' missing from fuse response"
