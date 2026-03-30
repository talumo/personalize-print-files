# tests/test_template_manager.py
import json, pytest, copy
from pathlib import Path
from template_manager import TemplateManager, ConfigError

MINIMAL_CONFIG = {
    "defaults": {
        "max_font_size": 72,
        "min_font_size": 18,
        "font_color": "#5A3E2B",
        "letter_spacing": 0,
        "dpi": 300
    },
    "theme_mapping": {
        "bunny-love": ["bunny", "bunny love"]
    },
    "themes": {
        "bunny-love": {
            "plate": {
                "template": "templates/bunny-love/plate.png",
                "text_box": {"x": 210, "y": 380, "width": 480, "height": 80}
            },
            "mug": {
                "template": "templates/bunny-love/mug.png",
                "text_box": {"x": 150, "y": 260, "width": 380, "height": 65},
                "letter_spacing": 6
            }
        }
    },
    "product_mapping": {
        "plate": ["plate"],
        "mug": ["mug"]
    }
}

@pytest.fixture
def config_file(tmp_path):
    # Create dummy template image files so validation passes
    tmpl_dir = tmp_path / "templates" / "bunny-love"
    tmpl_dir.mkdir(parents=True)
    (tmpl_dir / "plate.png").write_bytes(b"")
    (tmpl_dir / "mug.png").write_bytes(b"")

    cfg = copy.deepcopy(MINIMAL_CONFIG)
    # Point templates to tmp_path
    cfg["themes"]["bunny-love"]["plate"]["template"] = str(tmpl_dir / "plate.png")
    cfg["themes"]["bunny-love"]["mug"]["template"] = str(tmpl_dir / "mug.png")

    path = tmp_path / "template_config.json"
    path.write_text(json.dumps(cfg))
    return path

def test_resolve_plate(config_file):
    tm = TemplateManager(config_file)
    result = tm.resolve("Bunny Love Plate Set")
    assert result is not None
    assert result.product_key == "plate"
    assert result.dpi == 300
    assert result.letter_spacing == 0  # default

def test_resolve_mug_with_override(config_file):
    tm = TemplateManager(config_file)
    result = tm.resolve("Bunny Love Mug")
    assert result is not None
    assert result.product_key == "mug"
    assert result.letter_spacing == 6  # product-level override

def test_resolve_unknown_theme_returns_none(config_file):
    tm = TemplateManager(config_file)
    result = tm.resolve("Dinosaur Plate")
    assert result is None

def test_resolve_unknown_product_returns_none(config_file):
    tm = TemplateManager(config_file)
    result = tm.resolve("Bunny Love Sticker Sheet")
    assert result is None

def test_resolve_case_insensitive(config_file):
    tm = TemplateManager(config_file)
    assert tm.resolve("BUNNY LOVE PLATE SET") is not None

def test_missing_template_file_raises(tmp_path):
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    # Template file does NOT exist
    path = tmp_path / "template_config.json"
    path.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="template"):
        TemplateManager(path)
