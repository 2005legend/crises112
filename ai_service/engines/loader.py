"""
Model loader — loads all AI models on startup and tracks their health status.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ModelLoader:
    def __init__(self):
        self.stt_model = None
        self.embedding_model = None
        self.status = {
            "stt": "not_loaded",
            "vision": "not_loaded",
            "extraction": "not_loaded",
            "embedding": "not_loaded",
        }

    async def load_all(self):
        await self._load_stt()
        await self._load_embedding()
        # Vision uses NVIDIA NIM API (no local model needed)
        # Extraction uses Groq API (no local model needed)
        self.status["vision"] = "ready"
        self.status["extraction"] = "ready"

    async def _load_stt(self):
        try:
            from faster_whisper import WhisperModel
            self.stt_model = WhisperModel("medium", device="cpu", compute_type="int8")
            self.status["stt"] = "loaded"
            logger.info("Faster-Whisper model loaded (medium, cpu, int8)")
        except Exception as e:
            self.status["stt"] = "error"
            logger.error(f"Failed to load Faster-Whisper: {e}")

    async def _load_embedding(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            self.status["embedding"] = "loaded"
            logger.info("all-MiniLM-L6-v2 embedding model loaded")
        except Exception as e:
            self.status["embedding"] = "error"
            logger.error(f"Failed to load embedding model: {e}")
