import sys
from pathlib import Path

import pytest
from PIL import Image

# Ensure src is on the path (pytest.ini pythonpath handles it, this is a belt-and-suspenders backup)
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def tmp_image_dir(tmp_path):
    """Temp directory pre-populated with small valid image files."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for name in ["IMG_0001.jpg", "IMG_0002.jpg", "IMG_0003.png"]:
        img = Image.new("RGB", (10, 10), color=(100, 149, 237))
        img.save(images_dir / name)
    return images_dir


@pytest.fixture
def sample_model_list():
    """Realistic /v1/models payload with vision and non-vision models."""
    return {
        "data": [
            {"id": "qwen3-vl-8b"},
            {"id": "gemma4-e4b"},
            {"id": "qwen3.5-9b"},
            {"id": "deepseek-r1-14b"},
        ]
    }
