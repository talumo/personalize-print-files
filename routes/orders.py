import os

from flask import Blueprint, jsonify, render_template, request

import db
import job_queue
from shopify_client import ShopifyClient, ShopifyAuthError

orders_bp = Blueprint('orders', __name__)


def _get_client():
    token = db.get_setting('shopify_access_token')
    if not token:
        raise ValueError("Shopify not configured. Go to Settings to complete setup.")
    shop = db.get_setting('shopify_store', 'khd-kids.myshopify.com')
    version = db.get_setting('shopify_api_version', '2024-04')
    return ShopifyClient(token, shop, version)


@orders_bp.route('/')
@orders_bp.route('/orders')
def orders():
    host = request.args.get('host', '')
    api_key = os.environ.get('SHOPIFY_API_KEY', '')
    try:
        client = _get_client()
        all_orders = client.fetch_pending_orders()
        processed = db.get_processed_order_ids()
        pending = [o for o in all_orders if o.order_id not in processed]
    except ShopifyAuthError:
        pending = []
        error = "Shopify authentication failed. Check API credentials in Settings."
    except Exception as e:
        pending = []
        error = f"Error fetching orders: {str(e)}"
    else:
        error = None
    return render_template('orders.html',
                           orders=pending,
                           error=error,
                           host=host,
                           api_key=api_key)


@orders_bp.route('/api/orders/generate', methods=['POST'])
def generate():
    data = request.get_json(silent=True) or {}
    order_ids = data.get('order_ids', [])
    if not order_ids:
        return jsonify({'error': 'No orders selected'}), 400
    if not isinstance(order_ids, list) or not all(isinstance(oid, str) for oid in order_ids):
        return jsonify({'error': 'order_ids must be a list of strings'}), 400
    job_id = job_queue.enqueue(order_ids)
    return jsonify({'job_id': job_id})
