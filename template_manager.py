import json, logging
from pathlib import Path
from models import TemplateConfig

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    pass

class TemplateManager:
    def __init__(self, config_path):
        self._config_path = Path(config_path)
        data = json.loads(self._config_path.read_text(encoding="utf-8"))
        self._defaults = data.get("defaults", {})
        self._theme_mapping = data.get("theme_mapping", {})
        self._themes = data.get("themes", {})
        self._product_mapping = data.get("product_mapping", {})
        self._validate_templates()

    def _validate_templates(self):
        for theme, products in self._themes.items():
            for product_key, cfg in products.items():
                path = Path(cfg["template"])
                # Resolve relative to config file directory if not absolute
                if not path.is_absolute():
                    path = self._config_path.parent / path
                if not path.exists():
                    raise ConfigError(
                        f"Template file not found: {path} "
                        f"(theme={theme}, product={product_key})"
                    )

    def resolve(self, product_title: str):
        title_lower = product_title.lower().replace("-", " ")

        # Step 1: match theme
        theme_key = None
        for theme, keywords in self._theme_mapping.items():
            if any(kw.lower() in title_lower for kw in keywords):
                theme_key = theme
                break
        if theme_key is None:
            logger.warning("No theme matched for product title: %r", product_title)
            return None

        # Step 2: match product key
        product_key = None
        for key, keywords in self._product_mapping.items():
            if any(kw.lower() in title_lower for kw in keywords):
                product_key = key
                break
        if product_key is None:
            logger.warning("No product key matched for title: %r (theme=%s)",
                           product_title, theme_key)
            return None

        # Step 3: merge defaults + theme product config
        product_cfg = self._themes[theme_key].get(product_key, {})
        if not product_cfg:
            logger.warning("Product key %r not found in theme %r", product_key, theme_key)
            return None

        return TemplateConfig(
            template_path=product_cfg["template"],
            product_key=product_key,
            text_box=product_cfg["text_box"],
            max_font_size=product_cfg.get("max_font_size",
                          self._defaults.get("max_font_size", 72)),
            min_font_size=product_cfg.get("min_font_size",
                          self._defaults.get("min_font_size", 18)),
            font_color=product_cfg.get("font_color",
                       self._defaults.get("font_color", "#000000")),
            letter_spacing=product_cfg.get("letter_spacing",
                           self._defaults.get("letter_spacing", 0)),
            dpi=product_cfg.get("dpi", self._defaults.get("dpi", 300)),
        )
