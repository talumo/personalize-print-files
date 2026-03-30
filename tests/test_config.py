# tests/test_config.py
import os, pytest
from unittest.mock import patch

def test_config_loads_required_vars():
    env = {
        "SHOPIFY_ACCESS_TOKEN": "shpat_test",
        "SHOPIFY_STORE": "test.myshopify.com",
        "FONT_PATH": "fonts/test.ttf",
        "OUTPUT_DIR": "output",
    }
    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import config
        reload(config)
        cfg = config.load_config()
    assert cfg.shopify_access_token == "shpat_test"
    assert cfg.shopify_store == "test.myshopify.com"
    assert cfg.shopify_api_version == "2024-04"  # default
    assert cfg.font_path == "fonts/test.ttf"
    assert cfg.output_dir == "output"

def test_config_raises_on_missing_token():
    with patch.dict(os.environ, {}, clear=True):
        from importlib import reload
        import config
        reload(config)
        with pytest.raises(SystemExit):
            config.load_config()
