# Personalize Print Files

Generates print-ready PDFs for personalized Shopify tableware orders. Available as:

- **Embedded web app** — lives inside Shopify Admin, lets you select orders and download ZIPs from the browser
- **Batch CLI** — runs from the terminal or a cron job, processes all new orders automatically

Both modes use the same generation pipeline: fetch order → match product to template → composite name → export PDF → zip.

## How It Works

1. Fetches paid, unfulfilled Shopify orders with a "Personalization" line item property
2. Matches each product to a design theme + product template (plate, bowl, mug, placemat, spoon+fork)
3. Composites the name onto the base template image with auto font-sizing and configurable letter spacing
4. Exports a print-ready PDF at 300 DPI for each product
5. Zips each order's files for easy sharing or download

## Requirements

- Python 3.9+
- Your font file (.ttf or .otf)
- Template base images (see [Template Setup](#3-template-setup) below)

## Installation

```bash
pip install -r requirements.txt
```

---

## Embedded Web App

### 1. Create a Shopify App

In [Shopify Partner Dashboard](https://partners.shopify.com):

1. Apps → Create app → Custom app
2. Name it "Personalize Print Files"
3. Configuration → Admin API scopes → enable `read_orders`
4. Note the **API key** and **API secret** — you'll need them in the next step

### 2. Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```
SHOPIFY_API_KEY=your_api_key_here
SHOPIFY_API_SECRET=your_api_secret_here
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
APP_URL=https://your-app.up.railway.app
FONT_PATH=fonts/YourFont.ttf
OUTPUT_DIR=output
SHOPIFY_API_VERSION=2024-04
```

### 3. Template Setup

See [Template Setup](#3-template-setup) below — same process for both modes.

### 4. Deploy

**Railway (recommended):**

1. Push this repo to GitHub
2. New project in Railway → Deploy from GitHub repo
3. Add all variables from `.env` in Railway's Variables tab
4. Railway auto-detects the `Procfile` and starts the app

**Local with ngrok (for development):**

```bash
python app.py          # starts on http://localhost:5000
ngrok http 5000        # gives you https://abc123.ngrok.io
```

Set `APP_URL=https://abc123.ngrok.io` in `.env` and restart the app.

### 5. Configure App URL in Partner Dashboard

In your Shopify app's Configuration page:

- **App URL** → `https://your-app.up.railway.app/`
- **Allowed redirect URLs** → `https://your-app.up.railway.app/auth/callback`

### 6. Install the App

Visit the install URL to authorize:

```
https://your-app.up.railway.app/install?shop=your-store.myshopify.com
```

This kicks off the OAuth flow. After authorization you land on the Orders page inside Shopify Admin.

### 7. Create a Test Order

1. Shopify Admin → Orders → Create order → add a product
2. Add a line item property: **Name** = `Personalization`, **Value** = the customer's name (e.g. `Emma`)
3. Actions → Mark as paid
4. Open the app — the order appears in the list
5. Select it → Generate → download the ZIP when complete

### Updating the App

- Edit code locally → `pytest tests/ -q` → commit → push → Railway redeploys automatically
- To add a new API scope: update `scope` in `routes/auth.py`, update scopes in Partner Dashboard, then re-install the app so the merchant re-authorizes

---

## Batch CLI

### 1. Shopify Custom App

1. Shopify Admin → Settings → Apps and sales channels → Develop apps
2. Create an app named "Print File Generator"
3. Configuration → Admin API integration → enable `read_orders`
4. API credentials → Install app → copy the **Admin API access token**

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

See [Template Setup](#3-template-setup) below.

### 4. Usage

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

---

## Template Setup

For each product PSD:

1. Open in Photoshop, hide the name text layer (eye icon off)
2. File → Export → Export As → PNG, 300 DPI, **full canvas, no trimming**
3. Save to `templates/{theme-name}/{product-key}.png`
   - Theme name: lowercase with hyphens (e.g. `bunny-love`)
   - Product keys: `plate`, `bowl`, `mug`, `placemat`, `spoon_fork`
4. Note the text box position in pixel coordinates (x, y, width, height from top-left)
5. Add to `template_config.json` under `themes → {theme-name} → {product-key}`

> **Important:** Export the full canvas without trimming. Coordinates must match the exported image dimensions, not the PSD artboard.

### template_config.json

The scaffold `template_config.json` includes a `bunny-love` example. Update:

- `theme_mapping`: keywords to identify each theme from a Shopify product title
- `themes`: text box coordinates for each product
- `product_mapping`: keywords are already set for the 5 product types; add more if needed
- `defaults.letter_spacing`: adjust to taste (pixels between characters)
- `defaults.font_color`: hex color matching your design

In the web app you can also manage templates through the UI at `/templates`, or import from `template_config.json` via the Import button.

### Font File

Copy your `.ttf` or `.otf` file to the `fonts/` folder and set `FONT_PATH` in `.env`.

> **Unicode note:** The font must include all characters used in customer names. If a glyph is missing, Pillow renders a tofu box silently.

---

## Running Tests

```bash
pytest tests/ -q                        # all tests
pytest tests/test_auth.py -v            # OAuth flow
pytest tests/test_file_generator.py -v  # PDF generation
```

---

## Known Limitations

- **No OpenType kerning**: characters are drawn individually; compensate with `letter_spacing` in config
- **`--since` is UTC**: orders near midnight in non-UTC timezones may be included/excluded unexpectedly
- **Single name per order**: all products in one order share one name; multi-name bundles are not supported
- **In-memory job queue**: jobs in progress are lost if the server restarts
- **SQLite**: fine for a single-instance deployment; not suitable for multiple concurrent servers
