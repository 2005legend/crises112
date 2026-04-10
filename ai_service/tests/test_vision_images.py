"""
Manual image test for NVIDIA NIM vision engine.
Drop any image files into ai_service/tests/test_images/ and run:
    python -m pytest ai_service/tests/test_vision_images.py -v -s -m slow
"""
import asyncio
import os
import pytest
from pathlib import Path

from ai_service.engines.vision_engine import VisionEngine

TEST_IMAGES_DIR = Path(__file__).parent / "test_images"


def get_test_images():
    """Collect all image files from test_images directory."""
    if not TEST_IMAGES_DIR.exists():
        return []
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    return [f for f in TEST_IMAGES_DIR.iterdir() if f.suffix.lower() in extensions]


@pytest.mark.slow
@pytest.mark.parametrize("image_path", get_test_images(), ids=lambda p: p.name)
def test_vision_on_real_image(image_path):
    """
    Run NVIDIA NIM vision on a real image and print the result.
    Asserts the response is structurally valid — review the output manually.
    """
    engine = VisionEngine()
    image_bytes = image_path.read_bytes()

    print(f"\n{'='*60}")
    print(f"Image: {image_path.name}  ({len(image_bytes)//1024} KB)")
    print(f"{'='*60}")

    result = asyncio.run(engine.caption(image_bytes))

    print(f"Caption  : {result['caption']}")
    print(f"Entities : {result['entities']}")

    # Structural assertions
    assert isinstance(result["caption"], str), "caption must be a string"
    assert len(result["caption"]) > 5, "caption should not be empty"
    assert isinstance(result["entities"], list), "entities must be a list"


@pytest.mark.slow
def test_no_images_found_gives_clear_message():
    """Helpful message if test_images/ folder is empty or missing."""
    images = get_test_images()
    if not images:
        print(f"\nNo images found in {TEST_IMAGES_DIR}")
        print("Create the folder and drop .jpg/.png files in it:")
        print(f"  mkdir {TEST_IMAGES_DIR}")
        pytest.skip("No test images found — add images to ai_service/tests/test_images/")
