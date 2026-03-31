import logging, re, zipfile
from datetime import datetime
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import inch
from models import Order, GenerationResult
from text_renderer import render

logger = logging.getLogger(__name__)

def sanitize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9 _-]", "_", name)
    name = name[:40]
    name = name.strip("_").strip()
    return name if name else "unknown"

def generate_order(order: Order, template_manager, config) -> GenerationResult:
    # Determine folder name from first line item's name
    first_name = order.line_items[0].name if order.line_items else "unknown"
    names = {item.name for item in order.line_items}
    if len(names) > 1:
        logger.warning(
            "Order %s has differing personalization names %r — using first: %r",
            order.order_id, names, first_name
        )

    safe_name = sanitize_name(first_name)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    folder_name = f"ORDER-{order.order_id}_{safe_name}"
    order_dir = Path(config.output_dir) / date_str / folder_name
    order_dir.mkdir(parents=True, exist_ok=True)

    generated = skipped = failed = 0

    for item in order.line_items:
        tmpl = template_manager.resolve(item.title)
        if tmpl is None:
            logger.warning("Order %s: no template for %r — skipping",
                           order.order_id, item.title)
            skipped += 1
            continue
        try:
            composited = render(tmpl.template_path, item.name, tmpl, config.font_path)
            rgb = _flatten_to_rgb(composited)
            safe_item_name = sanitize_name(item.name)
            pdf_path = order_dir / f"{tmpl.product_key}_{safe_item_name}.pdf"
            _save_as_pdf(rgb, pdf_path, tmpl.dpi)
            generated += 1
        except Exception as e:
            logger.error("Order %s: failed to generate %r — %s",
                         order.order_id, item.title, e)
            failed += 1

    # Zip the order folder
    zip_path = order_dir.parent / f"{folder_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in order_dir.rglob("*"):
            zf.write(f, arcname=f.relative_to(order_dir.parent))

    return GenerationResult(
        order_id=order.order_id,
        files_generated=generated,
        files_skipped=skipped,
        files_failed=failed,
    )

def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    """Flatten RGBA onto white background for reportlab compatibility."""
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])
    return background

def _save_as_pdf(img: Image.Image, path: Path, dpi: int):
    width_pt = img.width / dpi * 72
    height_pt = img.height / dpi * 72
    c = rl_canvas.Canvas(str(path), pagesize=(width_pt, height_pt))
    c.drawInlineImage(img, 0, 0, width=width_pt, height=height_pt)
    c.save()
