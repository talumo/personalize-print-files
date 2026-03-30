import json
import pytest
from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setenv('SECRET_KEY', 'test-secret')
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_settings_page_renders(client):
    resp = client.get('/settings')
    assert resp.status_code == 200
    assert b'Settings' in resp.data
    assert b'Font path' in resp.data


def test_save_valid_settings(client):
    resp = client.post(
        '/api/settings',
        data=json.dumps({'font_path': 'fonts/Test.ttf', 'output_dir': 'out'}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert set(data['saved']) == {'font_path', 'output_dir'}


def test_saved_settings_appear_in_page(client):
    client.post(
        '/api/settings',
        data=json.dumps({'font_path': 'fonts/MyFont.ttf'}),
        content_type='application/json',
    )
    resp = client.get('/settings')
    assert b'fonts/MyFont.ttf' in resp.data


def test_unknown_setting_rejected(client):
    resp = client.post(
        '/api/settings',
        data=json.dumps({'evil_key': 'bad'}),
        content_type='application/json',
    )
    assert resp.status_code == 400
    assert 'Unknown setting' in resp.get_json()['error']


def test_save_api_version(client):
    resp = client.post(
        '/api/settings',
        data=json.dumps({'shopify_api_version': '2025-01'}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
