"""
Live smoke test for NVIDIA NIM vision engine (llama-3.2-11b-vision-instruct).
Run manually: python -m pytest ai_service/tests/test_vision_live.py -v -s -m slow
"""
import asyncio
import base64
import pytest

# Minimal 1x1 red JPEG (valid image, tiny size)
RED_PIXEL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
    "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgN"
    "DRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
    "MjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAA"
    "AAAAAAAAAAAAAAAAAP/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAAAAAAAAAA"
    "AAAA/9oADAMBAAIRAxEAPwCwABmX/9k="
)


@pytest.mark.slow
def test_nvidia_vision_api_responds():
    """Verify NVIDIA NIM vision API accepts a request and returns a valid response."""
    from ai_service.engines.vision_engine import VisionEngine

    image_bytes = base64.b64decode(RED_PIXEL_JPEG_B64)
    engine = VisionEngine()

    result = asyncio.run(engine.caption(image_bytes))

    print(f"\nCaption: {result['caption']}")
    print(f"Entities: {result['entities']}")

    assert isinstance(result["caption"], str)
    assert len(result["caption"]) > 0
    assert isinstance(result["entities"], list)
    # Should not be an error message for a valid image
    assert "error" not in result["caption"].lower() or "processing" not in result["caption"].lower()
