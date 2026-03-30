import json
import logging
from models import TemplateConfig
import db

logger = logging.getLogger(__name__)


class WebTemplateManager:
    """DB-backed TemplateManager. Same interface as template_manager.TemplateManager."""

    def resolve(self, product_title: str):
        """Match product title to a TemplateConfig, or return None."""
        title_lower = product_title.lower().replace('-', ' ')
        rows = db.get_all_templates()
        for row in rows:
            theme_kw = json.loads(row['theme_keywords'])
            prod_kw = json.loads(row['product_keywords'])
            theme_match = any(kw.lower() in title_lower for kw in theme_kw)
            product_match = any(kw.lower() in title_lower for kw in prod_kw)
            if theme_match and product_match:
                return TemplateConfig(
                    template_path=row['template_path'],
                    product_key=row['product_key'],
                    text_box=json.loads(row['text_box_json']),
                    max_font_size=row['max_font_size'],
                    min_font_size=row['min_font_size'],
                    font_color=row['font_color'],
                    letter_spacing=row['letter_spacing'],
                    dpi=row['dpi'],
                )
        logger.warning("No template matched for product title: %r", product_title)
        return None
