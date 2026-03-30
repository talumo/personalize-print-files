import hashlib
import hmac
import os
import re
import secrets

import requests
from flask import Blueprint, redirect, request, session, url_for

import db

auth_bp = Blueprint('auth', __name__)

SHOPIFY_SCOPES = 'read_orders'
VALID_SHOP_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$')


def _verify_hmac(params: dict, secret: str) -> bool:
    """Verify Shopify HMAC signature. Mutates params by removing 'hmac'."""
    received = params.pop('hmac', '')
    message = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    digest = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, received)


@auth_bp.route('/install')
def install():
    """Step 1: Redirect browser to Shopify OAuth consent page."""
    shop = request.args.get('shop', '').strip()
    if not VALID_SHOP_RE.match(shop):
        return 'Invalid shop domain', 400

    api_key = os.environ['SHOPIFY_API_KEY']
    app_url = os.environ['APP_URL']
    nonce = secrets.token_hex(16)
    session['oauth_nonce'] = nonce

    redirect_uri = f'{app_url}/auth/callback'
    auth_url = (
        f'https://{shop}/admin/oauth/authorize'
        f'?client_id={api_key}'
        f'&scope={SHOPIFY_SCOPES}'
        f'&redirect_uri={redirect_uri}'
        f'&state={nonce}'
    )
    return redirect(auth_url)


@auth_bp.route('/auth/callback')
def callback():
    """Step 2: Shopify redirects here with code. Exchange for access token."""
    params = dict(request.args)

    # Verify state (nonce) to prevent CSRF
    returned_state = params.get('state', '')
    expected_nonce = session.pop('oauth_nonce', None)
    if not expected_nonce or not hmac.compare_digest(returned_state, expected_nonce):
        return 'Invalid state parameter', 403

    # Verify HMAC
    secret = os.environ['SHOPIFY_API_SECRET']
    params_copy = dict(params)  # _verify_hmac mutates it
    if not _verify_hmac(params_copy, secret):
        return 'HMAC verification failed', 403

    shop = params.get('shop', '')
    if not VALID_SHOP_RE.match(shop):
        return 'Invalid shop domain', 400

    code = params.get('code', '')
    if not code:
        return 'Missing authorization code', 400

    # Exchange code for permanent access token
    api_key = os.environ['SHOPIFY_API_KEY']
    token_url = f'https://{shop}/admin/oauth/access_token'
    resp = requests.post(token_url, json={
        'client_id': api_key,
        'client_secret': secret,
        'code': code,
    }, timeout=10)
    resp.raise_for_status()
    access_token = resp.json()['access_token']

    # Persist to DB
    db.set_setting('shopify_access_token', access_token)
    db.set_setting('shopify_store', shop)
    db.set_setting('shopify_api_version',
                   db.get_setting('shopify_api_version', '2024-04'))

    # Store shop in session for subsequent requests
    session['shop'] = shop

    # Redirect into app — host param required by App Bridge
    host = request.args.get('host', '')
    return redirect(f'/orders?host={host}')
