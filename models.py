from dataclasses import dataclass

@dataclass
class LineItem:
    title: str   # Shopify product title, e.g. "Bunny Love Plate Set"
    name: str    # Personalization value, e.g. "Emma"

@dataclass
class Order:
    order_id: str
    order_number: str
    created_at: str          # ISO 8601 UTC string from Shopify
    line_items: list          # list[LineItem]

@dataclass
class TemplateConfig:
    template_path: str
    product_key: str          # e.g. "plate" — set by TemplateManager.resolve()
    text_box: dict            # {x, y, width, height} in pixels
    max_font_size: int
    min_font_size: int
    font_color: str           # hex e.g. "#5A3E2B"
    letter_spacing: int       # pixels between chars; 0 = no extra spacing
    dpi: int                  # print DPI, e.g. 300

@dataclass
class GenerationResult:
    order_id: str
    files_generated: int
    files_skipped: int
    files_failed: int
    # orders_processed is NOT here — aggregated by run_batch.py across all results
