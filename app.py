import json
import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__, template_folder='html_templates', static_folder='static')
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

    app.jinja_env.filters['from_json'] = json.loads

    from db import init_db, reset_stale_jobs
    init_db()
    reset_stale_jobs()  # Mark any 'running' jobs as 'failed' on startup

    from routes.auth import auth_bp
    from routes.orders import orders_bp
    from routes.jobs import jobs_bp
    from routes.downloads import downloads_bp
    from routes.templates_routes import templates_bp
    from routes.settings_routes import settings_bp

    for bp in [auth_bp, orders_bp, jobs_bp, downloads_bp, templates_bp, settings_bp]:
        app.register_blueprint(bp)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', port=5000)
