import json
import os
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_file

import db

downloads_bp = Blueprint('downloads', __name__)


@downloads_bp.route('/downloads')
def downloads():
    host = request.args.get('host', '')
    api_key = os.environ.get('SHOPIFY_API_KEY', '')
    job_id = request.args.get('job_id')  # may be set right after generation
    jobs = db.get_all_jobs(limit=20)
    current_job = db.get_job(job_id) if job_id else None
    return render_template('downloads.html',
                           jobs=jobs,
                           current_job=current_job,
                           job_id=job_id,
                           host=host,
                           api_key=api_key)


@downloads_bp.route('/api/jobs/<job_id>/download')
def download_zip(job_id):
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    if job['status'] != 'complete':
        return jsonify({'error': 'Job not complete'}), 400

    result = json.loads(job['result_json'] or '{}')
    zip_paths = result.get('zip_paths', [])

    if not zip_paths:
        return jsonify({'error': 'No files generated for this job'}), 404

    if len(zip_paths) == 1:
        path = Path(zip_paths[0])
        if not path.exists():
            return jsonify({'error': 'File not found on disk'}), 404
        return send_file(str(path), as_attachment=True,
                         download_name=path.name)

    # Multiple orders — create a combined zip on the fly
    import io, zipfile
    combined = io.BytesIO()
    with zipfile.ZipFile(combined, 'w', zipfile.ZIP_DEFLATED) as zf:
        for zp in zip_paths:
            p = Path(zp)
            if p.exists():
                zf.write(zp, arcname=p.name)
    combined.seek(0)
    return send_file(combined, as_attachment=True,
                     download_name=f'orders-{job_id[:8]}.zip',
                     mimetype='application/zip')


@downloads_bp.route('/api/jobs/<job_id>/reset', methods=['POST'])
def reset_job_orders(job_id):
    """Remove all orders in a job from processed_orders so they reappear as pending."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    import json as _json
    order_ids = _json.loads(job['order_ids'] or '[]')
    for order_id in order_ids:
        db.unmark_processed(order_id)
    return jsonify({'ok': True, 'reset': order_ids})
