# tests/test_models.py
from models import LineItem, Order, TemplateConfig, GenerationResult

def test_line_item_fields():
    item = LineItem(title="Bunny Love Plate Set", name="Emma")
    assert item.title == "Bunny Love Plate Set"
    assert item.name == "Emma"

def test_order_fields():
    item = LineItem(title="Bunny Love Plate Set", name="Emma")
    order = Order(order_id="1234", order_number="#1234",
                  created_at="2026-03-25T10:00:00Z", line_items=[item])
    assert order.order_id == "1234"
    assert len(order.line_items) == 1

def test_template_config_fields():
    cfg = TemplateConfig(
        template_path="templates/bunny-love/plate.png",
        product_key="plate",
        text_box={"x": 210, "y": 380, "width": 480, "height": 80},
        max_font_size=72, min_font_size=18,
        font_color="#5A3E2B", letter_spacing=4, dpi=300
    )
    assert cfg.product_key == "plate"
    assert cfg.dpi == 300

def test_generation_result_defaults():
    result = GenerationResult(order_id="1234",
                               files_generated=2, files_skipped=1, files_failed=0)
    assert result.files_generated == 2
    assert result.files_failed == 0
