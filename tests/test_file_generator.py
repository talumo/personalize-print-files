# tests/test_file_generator.py
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image
from models import Order, LineItem, TemplateConfig, GenerationResult
from file_generator import sanitize_name, generate_order

# --- sanitize_name tests ---

def test_sanitize_normal_name():
    assert sanitize_name("Emma") == "Emma"

def test_sanitize_strips_unsafe_chars():
    result = sanitize_name("Chloë/test")
    assert "/" not in result
    assert len(result) > 0

def test_sanitize_truncates_to_40():
    long_name = "A" * 50
    assert len(sanitize_name(long_name)) <= 40

def test_sanitize_empty_fallback():
    assert sanitize_name("!!!") == "unknown"
    assert sanitize_name("   ") == "unknown"

def test_sanitize_strips_edge_underscores():
    result = sanitize_name("!!Emma!!")
    assert not result.startswith("_")
    assert not result.endswith("_")

# --- generate_order tests ---

def _make_template_config(tmp_path):
    # Create a real small base image for the test
    img_path = tmp_path / "plate.png"
    Image.new("RGBA", (100, 100), (255, 255, 255, 255)).save(img_path)
    return TemplateConfig(
        template_path=str(img_path),
        product_key="plate",
        text_box={"x": 10, "y": 10, "width": 80, "height": 30},
        max_font_size=24, min_font_size=8,
        font_color="#000000", letter_spacing=0, dpi=300,
    )

def test_generate_order_creates_pdf_and_zip(tmp_path):
    cfg_mock = MagicMock()
    cfg_mock.font_path = ""
    cfg_mock.output_dir = str(tmp_path / "output")

    tmpl_cfg = _make_template_config(tmp_path)
    tm = MagicMock()
    tm.resolve.return_value = tmpl_cfg

    order = Order(
        order_id="1001", order_number="#1001",
        created_at="2026-03-25T10:00:00Z",
        line_items=[LineItem(title="Bunny Love Plate Set", name="Emma")]
    )

    result = generate_order(order, tm, cfg_mock)

    assert result.files_generated == 1
    assert result.files_skipped == 0
    assert result.files_failed == 0

    # Check PDF exists
    output_root = Path(cfg_mock.output_dir)
    pdfs = list(output_root.rglob("*.pdf"))
    assert len(pdfs) == 1
    assert pdfs[0].name == "plate_Emma.pdf"

    # Check zip exists
    zips = list(output_root.rglob("*.zip"))
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as z:
        assert any(n.endswith("plate_Emma.pdf") for n in z.namelist())

def test_same_product_different_names_generates_both(tmp_path):
    """Two bowls in one order (Liam + William) must produce two separate PDFs."""
    cfg_mock = MagicMock()
    cfg_mock.font_path = ""
    cfg_mock.output_dir = str(tmp_path / "output")

    tmpl_cfg = _make_template_config(tmp_path)
    tmpl_cfg = TemplateConfig(
        template_path=tmpl_cfg.template_path,
        product_key="bowl",
        text_box=tmpl_cfg.text_box,
        max_font_size=tmpl_cfg.max_font_size,
        min_font_size=tmpl_cfg.min_font_size,
        font_color=tmpl_cfg.font_color,
        letter_spacing=tmpl_cfg.letter_spacing,
        dpi=tmpl_cfg.dpi,
    )
    tm = MagicMock()
    tm.resolve.return_value = tmpl_cfg

    order = Order(
        order_id="3001", order_number="#3001",
        created_at="2026-03-31T10:00:00Z",
        line_items=[
            LineItem(title="Airplane Kids Dinnerware Bowl", name="Liam"),
            LineItem(title="Airplane Kids Dinnerware Bowl", name="William"),
        ]
    )
    result = generate_order(order, tm, cfg_mock)

    assert result.files_generated == 2
    output_root = Path(cfg_mock.output_dir)
    pdfs = {p.name for p in output_root.rglob("*.pdf")}
    assert "bowl_Liam.pdf" in pdfs
    assert "bowl_William.pdf" in pdfs


def test_unresolved_product_counted_as_skipped(tmp_path):
    cfg_mock = MagicMock()
    cfg_mock.font_path = ""
    cfg_mock.output_dir = str(tmp_path / "output")

    tm = MagicMock()
    tm.resolve.return_value = None   # no template match

    order = Order(
        order_id="1002", order_number="#1002",
        created_at="2026-03-25T10:00:00Z",
        line_items=[LineItem(title="Unknown Sticker", name="Emma")]
    )
    result = generate_order(order, tm, cfg_mock)
    assert result.files_skipped == 1
    assert result.files_generated == 0

def test_differing_names_uses_first_logs_warning(tmp_path, caplog):
    import logging
    cfg_mock = MagicMock()
    cfg_mock.font_path = ""
    cfg_mock.output_dir = str(tmp_path / "output")

    tmpl_cfg = _make_template_config(tmp_path)
    tm = MagicMock()
    tm.resolve.return_value = tmpl_cfg

    order = Order(
        order_id="1003", order_number="#1003",
        created_at="2026-03-25T10:00:00Z",
        line_items=[
            LineItem(title="Bunny Love Plate Set", name="Emma"),
            LineItem(title="Bunny Love Mug", name="Sophie"),  # different name
        ]
    )
    with caplog.at_level(logging.WARNING):
        result = generate_order(order, tm, cfg_mock)
    assert "differing" in caplog.text.lower() or "different" in caplog.text.lower()
