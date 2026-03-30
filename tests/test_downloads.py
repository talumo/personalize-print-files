import json
import pytest
import db as db_module


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'test')
    monkeypatch.setenv('SHOPIFY_API_KEY', 'k')
    monkeypatch.setenv('SHOPIFY_API_SECRET', 's')
    monkeypatch.setenv('APP_URL', 'https://x.com')
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setattr(db_module, 'DB_PATH', str(tmp_path / 'test.db'))
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_downloads_page_loads(app_client):
    resp = app_client.get('/downloads')
    assert resp.status_code == 200


def test_download_zip_not_found(app_client):
    resp = app_client.get('/api/jobs/nonexistent/download')
    assert resp.status_code == 404


def test_download_zip_not_complete(app_client):
    db_module.create_job('j1', ['1001'], 'pending')
    resp = app_client.get('/api/jobs/j1/download')
    assert resp.status_code == 400


def test_template_list_loads(app_client):
    resp = app_client.get('/templates')
    assert resp.status_code == 200


def test_template_save_missing_keys(app_client):
    resp = app_client.post('/api/templates', data={})
    assert resp.status_code == 400


def test_template_delete(app_client, tmp_path):
    img = tmp_path / 'plate.png'
    img.write_bytes(b'')
    db_module.upsert_template(
        'bunny', 'plate', str(img), '{"x":0,"y":0,"width":100,"height":50}',
        72, 18, '#000', 0, 300, '["bunny"]', '["plate"]'
    )
    resp = app_client.delete('/api/templates/bunny/plate')
    assert resp.status_code == 200
    assert db_module.get_template('bunny', 'plate') is None


def test_import_json(app_client):
    resp = app_client.post('/api/templates/import-json',
                           data={'json_path': 'template_config.json'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['imported'] > 0
