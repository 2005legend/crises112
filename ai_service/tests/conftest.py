"""
Shared fixtures for AI service tests.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from ai_service.main import app


@pytest.fixture
def mock_models():
    """Inject lightweight mock models into app state."""
    loader = MagicMock()
    loader.stt_model = MagicMock()
    loader.embedding_model = MagicMock()
    loader.embedding_model.encode.return_value = np.array([1.0, 0.0, 0.0])
    loader.status = {
        "stt": "loaded",
        "vision": "ready",
        "extraction": "ready",
        "embedding": "loaded",
    }
    app.state.models = loader
    return loader


@pytest.fixture
def client(mock_models):
    return TestClient(app, raise_server_exceptions=False)
