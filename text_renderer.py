import logging
from PIL import Image, ImageDraw, ImageFont
from models import TemplateConfig

logger = logging.getLogger(__name__)

def measure_text_width(text: str, font, letter_spacing: int = 0) -> int:
    total = 0
    for i, char in enumerate(text):
        bbox = font.getbbox(char)
        total += bbox[2]  # right edge = character width
        if i < len(text) - 1:
            total += letter_spacing
    return total

def render(base_image_path: str, name: str, config: TemplateConfig,
           font_path: str) -> Image.Image:
    """font_path comes from Config (env), not TemplateConfig, to keep concerns separated."""
    name = name.strip()
    if not name:
        raise ValueError("Personalization name is empty after stripping whitespace")

    img = Image.open(base_image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size
    logger.info("Rendering %r onto image %dx%d, font=%r", name, img_w, img_h, font_path)

    box = config.text_box
    font_size = config.max_font_size
    font = None
    total_width = None
    font_loaded_ok = False

    # Auto-size: reduce until text fits box width
    while font_size >= config.min_font_size:
        try:
            font = ImageFont.truetype(font_path, font_size)
            font_loaded_ok = True
        except (AttributeError, OSError) as e:
            logger.warning("Font load failed (%s), using default", e)
            font = ImageFont.load_default()
        total_width = measure_text_width(name, font, config.letter_spacing)
        if total_width <= box["width"]:
            break
        font_size -= 2

    if total_width > box["width"]:
        logger.warning(
            "Name %r exceeds text box width at min font size %d — rendering at min size",
            name, config.min_font_size
        )

    # Parse font color
    hex_color = config.font_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    fill = (r, g, b, 255)

    # Center text block in box
    font_height = font.getbbox("A")[3]  # approximate cap height
    x = box["x"] + (box["width"] - total_width) // 2
    y = box["y"] + (box["height"] - font_height) // 2

    logger.info(
        "Text box: x=%d y=%d w=%d h=%d | font_size=%d font_ok=%s | "
        "text_w=%d text_h=%d | draw_at=(%d,%d) | color=%s | image=%dx%d",
        box["x"], box["y"], box["width"], box["height"],
        font_size, font_loaded_ok,
        total_width, font_height,
        x, y, config.font_color,
        img_w, img_h,
    )

    if x < 0 or y < 0 or x >= img_w or y >= img_h:
        logger.warning("draw_at (%d,%d) is outside image bounds %dx%d — text will not be visible", x, y, img_w, img_h)

    # Draw character by character with letter spacing
    cursor_x = x
    for char in name:
        draw.text((cursor_x, y), char, font=font, fill=fill)
        char_width = font.getbbox(char)[2]
        cursor_x += char_width + config.letter_spacing

    return img
