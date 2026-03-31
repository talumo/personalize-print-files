import json
import os
from pathlib import Path
from werkzeug.utils import secure_filename

from flask import (Blueprint, jsonify, redirect, render_template,
                   request, url_for)

import db

templates_bp = Blueprint('templates', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'}
# Default to a subfolder of the data volume so uploads survive redeploys.
# Set UPLOAD_FOLDER env var to override (e.g. /app/data/uploads on Railway).
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')


def _allowed_image(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@templates_bp.route('/templates')
def template_list():
    host = request.args.get('host', '')
    api_key = os.environ.get('SHOPIFY_API_KEY', '')
    rows = db.get_all_templates()
    # Group by theme_key
    themes = {}
    for row in rows:
        t = row['theme_key']
        themes.setdefault(t, []).append(row)
    return render_template('template_list.html',
                           themes=themes,
                           host=host,
                           api_key=api_key)


@templates_bp.route('/templates/new')
def template_new():
    host = request.args.get('host', '')
    api_key = os.environ.get('SHOPIFY_API_KEY', '')
    return render_template('template_editor.html',
                           template=None,
                           host=host,
                           api_key=api_key)


@templates_bp.route('/templates/<theme_key>/<product_key>/edit')
def template_edit(theme_key, product_key):
    host = request.args.get('host', '')
    api_key = os.environ.get('SHOPIFY_API_KEY', '')
    tmpl = db.get_template(theme_key, product_key)
    if not tmpl:
        return 'Template not found', 404
    return render_template('template_editor.html',
                           template=tmpl,
                           host=host,
                           api_key=api_key)


@templates_bp.route('/api/templates', methods=['POST'])
def template_save():
    """Save (create or update) a template. Handles image upload."""
    theme_key = request.form.get('theme_key', '').strip()
    product_key = request.form.get('product_key', '').strip()
    if not theme_key or not product_key:
        return jsonify({'error': 'theme_key and product_key are required'}), 400

    # Handle image upload
    template_path = request.form.get('template_path_existing', '')
    if 'template_image' in request.files:
        f = request.files['template_image']
        if f and f.filename and _allowed_image(f.filename):
            filename = secure_filename(f.filename)
            theme_dir = Path(UPLOAD_FOLDER) / theme_key
            theme_dir.mkdir(parents=True, exist_ok=True)
            save_path = theme_dir / filename
            f.save(str(save_path))
            template_path = str(save_path.resolve())

    if not template_path:
        return jsonify({'error': 'Template image is required'}), 400

    text_box = {
        'x': int(request.form.get('x', 0)),
        'y': int(request.form.get('y', 0)),
        'width': int(request.form.get('width', 100)),
        'height': int(request.form.get('height', 50)),
    }

    db.upsert_template(
        theme_key=theme_key,
        product_key=product_key,
        template_path=template_path,
        text_box_json=json.dumps(text_box),
        max_font_size=int(request.form.get('max_font_size', 72)),
        min_font_size=int(request.form.get('min_font_size', 18)),
        font_color=request.form.get('font_color', '#5A3E2B'),
        letter_spacing=int(request.form.get('letter_spacing', 0)),
        dpi=int(request.form.get('dpi', 300)),
        theme_keywords=request.form.get('theme_keywords', '[]'),
        product_keywords=request.form.get('product_keywords', '[]'),
    )
    return jsonify({'ok': True, 'theme_key': theme_key, 'product_key': product_key})


@templates_bp.route('/api/templates/<theme_key>/<product_key>', methods=['DELETE'])
def template_delete(theme_key, product_key):
    db.delete_template(theme_key, product_key)
    return jsonify({'ok': True})


@templates_bp.route('/api/templates/import-json', methods=['POST'])
def import_json():
    """Import from template_config.json into the DB."""
    json_path = request.form.get('json_path', 'template_config.json')
    try:
        count = db.import_from_json(json_path)
        return jsonify({'ok': True, 'imported': count})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
