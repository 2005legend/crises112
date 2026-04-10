"""
Live smoke test for Faster-Whisper medium model.
Generates a synthetic WAV (sine wave) and verifies the model loads + runs.
Run manually: python -m pytest ai_service/tests/test_stt_live.py -v -s
"""
import struct
import math
import pytest
from faster_whisper import WhisperModel
from ai_service.engines.stt_engine import STTEngine


def generate_sine_wav(frequency=440, duration_s=1, sample_rate=16000) -> bytes:
    """Generate a minimal valid WAV file with a sine tone."""
    num_samples = int(sample_rate * duration_s)
    samples = [int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate)) for i in range(num_samples)]
    data = struct.pack(f"<{num_samples}h", *samples)

    # WAV header
    data_size = len(data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1,          # PCM, mono
        sample_rate, sample_rate * 2,
        2, 16,                       # block align, bits per sample
        b"data", data_size,
    )
    return header + data


@pytest.mark.slow
def test_medium_model_loads():
    """Verify medium model loads without error."""
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    assert model is not None


@pytest.mark.slow
def test_medium_model_transcribes_sine_wave():
    """
    Sine wave has no speech — VAD should filter it out and return empty transcript.
    This confirms the pipeline runs end-to-end without crashing.
    """
    model = WhisperModel("medium", device="cpu", compute_type="int8")
    engine = STTEngine(model)
    wav_bytes = generate_sine_wav()
    result = engine.transcribe(wav_bytes, filename="test_tone.wav")

    print(f"\nTranscript: '{result['transcript']}'")
    print(f"Language: {result['language_detected']}")

    # Sine wave = no speech, so transcript should be empty (VAD filters it)
    assert isinstance(result["transcript"], str)
    assert isinstance(result["language_detected"], str)
    # No crash = success
