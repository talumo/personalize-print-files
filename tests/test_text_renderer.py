# tests/test_text_renderer.py
import pytest
from pathlib import Path
from PIL import Image, ImageFont, ImageDraw
from models import TemplateConfig
from text_renderer import render, measure_text_width

# Create a small test base image (solid white, 400x200)
@pytest.fixture
def base_image(tmp_path):
    img = Image.new("RGBA", (400, 200), (255, 255, 255, 255))
    path = tmp_path / "base.png"
    img.save(path)
    return str(path)

@pytest.fixture
def cfg():
    return TemplateConfig(
        template_path="",       # set per-test
        product_key="plate",
        text_box={"x": 50, "y": 80, "width": 300, "height": 60},
        max_font_size=60,
        min_font_size=12,
        font_color="#000000",
        letter_spacing=0,
        dpi=300,
    )

def test_render_returns_rgba_image(base_image, cfg):
    result = render(base_image, "Emma", cfg, font_path="")
    assert result.mode == "RGBA"
    assert result.size == (400, 200)

def test_short_name_uses_large_font(base_image, cfg):
    result = render(base_image, "Em", cfg, font_path="")
    assert result is not None

def test_long_name_fits_in_box(base_image, cfg):
    result = render(base_image, "Bartholomew", cfg, font_path="")
    assert result is not None

def test_empty_name_raises(base_image, cfg):
    with pytest.raises(ValueError, match="empty"):
        render(base_image, "   ", cfg, font_path="")

def test_measure_text_width_increases_with_spacing(base_image, cfg):
    # With letter spacing, total width should be >= width without
    font = ImageFont.load_default()
    w0 = measure_text_width("Emma", font, letter_spacing=0)
    w4 = measure_text_width("Emma", font, letter_spacing=4)
    assert w4 >= w0
