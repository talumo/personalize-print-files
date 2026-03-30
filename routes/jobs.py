from flask import Blueprint, jsonify
import db

jobs_bp = Blueprint('jobs', __name__)


@jobs_bp.route('/api/jobs/<job_id>')
def job_status(job_id):
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(dict(job))
