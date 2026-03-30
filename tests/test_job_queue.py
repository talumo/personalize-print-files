import json
import pytest
import db as db_module
from unittest.mock import patch, MagicMock


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'test.db')
    monkeypatch.setenv('DB_PATH', db_path)
    monkeypatch.setattr(db_module, 'DB_PATH', db_path)
    db_module.init_db()
    return db_path


def test_enqueue_creates_job(isolated_db):
    import job_queue
    with patch.object(job_queue._queue, 'put'):  # don't actually process
        job_id = job_queue.enqueue(['1001', '1002'])
    job = db_module.get_job(job_id)
    assert job is not None
    assert job['status'] == 'pending'
    assert json.loads(job['order_ids']) == ['1001', '1002']


def test_web_template_manager_resolve_match(isolated_db):
    db_module.upsert_template(
        theme_key='bunny-love', product_key='plate',
        template_path='/tmp/plate.png',
        text_box_json='{"x":10,"y":10,"width":100,"height":50}',
        max_font_size=72, min_font_size=18,
        font_color='#000', letter_spacing=0, dpi=300,
        theme_keywords='["bunny"]',
        product_keywords='["plate"]',
    )
    from web_template_manager import WebTemplateManager
    tm = WebTemplateManager()
    result = tm.resolve('Bunny Love Plate Set')
    assert result is not None
    assert result.product_key == 'plate'
    assert result.dpi == 300


def test_web_template_manager_resolve_no_match(isolated_db):
    from web_template_manager import WebTemplateManager
    tm = WebTemplateManager()
    result = tm.resolve('Unknown Product')
    assert result is None


def test_job_status_api(isolated_db, monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test')
    monkeypatch.setenv('SHOPIFY_API_KEY', 'k')
    monkeypatch.setenv('SHOPIFY_API_SECRET', 's')
    monkeypatch.setenv('APP_URL', 'https://x.com')
    from app import create_app
    app = create_app()
    with app.test_client() as c:
        db_module.create_job('test-job-123', ['1001'], 'pending')
        resp = c.get('/api/jobs/test-job-123')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['job_id'] == 'test-job-123'
        assert data['status'] == 'pending'

        resp404 = c.get('/api/jobs/nonexistent')
        assert resp404.status_code == 404
