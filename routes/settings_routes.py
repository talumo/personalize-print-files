import os

from flask import Blueprint, jsonify, render_template, request

import db

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings')
def settings():
    host = request.args.get('host', '')
    api_key = os.environ.get('SHOPIFY_API_KEY', '')
    saved = db.get_all_settings()
    return render_template('settings.html',
                           settings=saved,
                           host=host,
                           api_key=api_key)


@settings_bp.route('/api/settings', methods=['POST'])
def save_settings():
    allowed = {'font_path', 'output_dir', 'shopify_api_version'}
    data = request.get_json(force=True) or {}
    saved = []
    for key, value in data.items():
        if key not in allowed:
            return jsonify({'error': f'Unknown setting: {key}'}), 400
        db.set_setting(key, str(value).strip())
        saved.append(key)
    return jsonify({'ok': True, 'saved': saved})
