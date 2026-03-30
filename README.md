# Personalize Print Files

Batch CLI tool that generates print-ready PDFs for personalized Shopify tableware orders.
Enter a name once per order — get one PDF per product, ready to send to your print partner.

## How It Works

1. Fetches paid, unfulfilled Shopify orders with a "Personalization" line item property
2. Matches each product to a design theme + product template (plate, bowl, mug, placemat, spoon+fork)
3. Composites the name onto the base template image with auto font-sizing and configurable letter spacing
4. Exports a print-ready PDF at 300 DPI for each product
5. Zips each order's files for easy sharing or download

## Requirements

- Python 3.9+
- Your font file (.ttf or .otf)
- Template base images (see Template Setup below)

## Installation

```bash
pip install -r requirements.txt
```

## Setup

### 1. Shopify Custom App

1. Shopify Admin → Settings → Apps and sales channels → Develop apps
2. Create an app named "Print File Generator"
3. Configuration → Admin API integration → enable `read_orders`
4. API credentials → Install app → copy the Admin API access token

### 2. Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:
```
SHOPIFY_ACCESS_TOKEN=shpat_...
SHOPIFY_STORE=your-store.myshopify.com
SHOPIFY_API_VERSION=2024-04
FONT_PATH=fonts/YourFont.ttf
OUTPUT_DIR=output
```

Update `SHOPIFY_API_VERSION` when Shopify notifies you of deprecations (check quarterly at shopify.dev/changelog).

### 3. Template Setup

For each product PSD:
1. Open in Photoshop, hide the name text layer (eye icon off)
2. File → Export → Export As → PNG, 300 DPI, **full canvas, no trimming**
3. Save to `templates/{theme-name}/{product-key}.png`
   - Theme name: lowercase with hyphens (e.g. `bunny-love`)
   - Product keys: `plate`, `bowl`, `mug`, `placemat`, `spoon_fork`
4. Note the text box position in pixel coordinates (x, y, width, height from top-left)
5. Add to `template_config.json` under `themes → {theme-name} → {product-key}`

> **Important:** Export the full canvas without trimming. Coordinates must match the exported image dimensions, not the PSD artboard.

### 4. template_config.json

The scaffold `template_config.json` includes a `bunny-love` example. Update:
- `theme_mapping`: add keywords to identify each theme from a Shopify product title
- `themes`: add text box coordinates for each product
- `product_mapping`: keywords are already set for the 5 product types; add more if needed
- `defaults.letter_spacing`: adjust to taste (pixels between characters)
- `defaults.font_color`: hex color matching your design

### 5. Add Font File

Copy your `.ttf` or `.otf` file to the `fonts/` folder and set `FONT_PATH` in `.env`.

> **Unicode note:** The font must include all characters used in customer names. If a glyph is missing, Pillow renders a tofu box silently.

## Usage

```bash
# Process all new paid orders
python run_batch.py

# Preview without generating files
python run_batch.py --dry-run

# Reprocess a specific order
python run_batch.py --order 12345

# Only fetch orders since a date (UTC)
python run_batch.py --since 2026-03-01
```

Output is saved to `output/YYYY-MM-DD/ORDER-{id}_{name}/` with one PDF per product, plus a `.zip` of each order folder.

## Known Limitations

- **No OpenType kerning**: characters are drawn individually; compensate with `letter_spacing` in config
- **`--since` is UTC**: orders near midnight in non-UTC timezones may be included/excluded unexpectedly
- **Single name per order**: all products in one order share one name; multi-name bundles are not supported
