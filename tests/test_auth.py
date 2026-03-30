import os
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('SHOPIFY_API_KEY', 'test_api_key')
    monkeypatch.setenv('SHOPIFY_API_SECRET', 'test_api_secret')
    monkeypatch.setenv('APP_URL', 'https://test.example.com')
    monkeypatch.setenv('SECRET_KEY', 'test-secret')
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'test.db'))
    import db as db_module
    monkeypatch.setattr(db_module, 'DB_PATH', str(tmp_path / 'test.db'))
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c

def test_install_redirects_to_shopify(client):
    resp = client.get('/install?shop=test-store.myshopify.com')
    assert resp.status_code == 302
    assert 'test-store.myshopify.com' in resp.headers['Location']
    assert 'test_api_key' in resp.headers['Location']

def test_install_rejects_invalid_shop(client):
    resp = client.get('/install?shop=evil.com')
    assert resp.status_code == 400

def test_install_rejects_missing_shop(client):
    resp = client.get('/install')
    assert resp.status_code == 400

def test_callback_verifies_hmac(client):
    # Bad HMAC should return 403
    resp = client.get('/auth/callback?shop=test.myshopify.com&code=abc&hmac=bad&state=xyz')
    assert resp.status_code == 403

def test_callback_verifies_nonce(client):
    # No session nonce set — state mismatch → 403
    import hmac as hmac_lib, hashlib
    params = {'shop': 'test.myshopify.com', 'code': 'abc', 'state': 'wrongnonce'}
    msg = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    sig = hmac_lib.new(b'test_api_secret', msg.encode(), hashlib.sha256).hexdigest()
    resp = client.get(f'/auth/callback?shop=test.myshopify.com&code=abc&state=wrongnonce&hmac={sig}')
    assert resp.status_code == 403
