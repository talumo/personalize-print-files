# tests/test_shopify_client.py
import pytest
from unittest.mock import patch, MagicMock
from models import Order, LineItem
from shopify_client import ShopifyClient, ShopifyAuthError

MOCK_ORDER = {
    "id": 1001,
    "order_number": "#1001",
    "created_at": "2026-03-25T10:00:00Z",
    "line_items": [
        {
            "title": "Bunny Love Plate Set",
            "properties": [{"name": "Personalization", "value": "Emma"}]
        },
        {
            "title": "Bunny Love Mug",
            "properties": [{"name": "Personalization", "value": "Emma"}]
        },
        {
            "title": "Plain Sticker Sheet",  # no personalization
            "properties": []
        }
    ]
}

def make_client():
    return ShopifyClient(
        access_token="shpat_test",
        store="test.myshopify.com",
        api_version="2024-04"
    )

def mock_response(json_data, status=200, link_header=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.headers = {"Link": link_header} if link_header else {}
    return resp

def test_fetch_returns_orders_with_personalization():
    client = make_client()
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [MOCK_ORDER]})):
        orders = client.fetch_pending_orders()
    assert len(orders) == 1
    order = orders[0]
    assert order.order_id == "1001"
    assert len(order.line_items) == 2  # sticker sheet excluded (no personalization)
    assert order.line_items[0].name == "Emma"

def test_fetch_since_date():
    client = make_client()
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": []})) as mock_get:
        client.fetch_pending_orders(since_date="2026-03-01")
    call_url = mock_get.call_args[0][0]
    assert "created_at_min=2026-03-01T00%3A00%3A00Z" in call_url or \
           "created_at_min" in call_url

def test_auth_error_raises():
    client = make_client()
    with patch("shopify_client.requests.get",
               return_value=mock_response({}, status=401)):
        with pytest.raises(ShopifyAuthError):
            client.fetch_pending_orders()

def test_fetch_single_order():
    client = make_client()
    with patch("shopify_client.requests.get",
               return_value=mock_response({"order": MOCK_ORDER})):
        orders = client.fetch_order_by_id("1001")
    assert len(orders) == 1
    assert orders[0].order_id == "1001"

def test_personalization_key_case_insensitive():
    order_data = {
        **MOCK_ORDER,
        "line_items": [{
            "title": "Bunny Love Plate Set",
            "properties": [{"name": "personalisation", "value": "Sofía"}]
        }]
    }
    client = make_client()
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    assert orders[0].line_items[0].name == "Sofía"

def test_personalization_key_with_single_colon():
    order_data = {
        **MOCK_ORDER,
        "line_items": [{
            "title": "Bunny Love Plate Set",
            "properties": [{"name": "Personalization:", "value": "Tristan"}]
        }]
    }
    client = make_client()
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    assert orders[0].line_items[0].name == "Tristan"

def test_personalization_key_with_double_colon():
    order_data = {
        **MOCK_ORDER,
        "line_items": [{
            "title": "Bunny Love Plate Set",
            "properties": [{"name": "Personalization::", "value": "Lily"}]
        }]
    }
    client = make_client()
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    assert orders[0].line_items[0].name == "Lily"

def test_rate_limit_retries(monkeypatch):
    client = make_client()
    responses = [
        mock_response({}, status=429),
        mock_response({}, status=429),
        mock_response({"orders": [MOCK_ORDER]}, status=200),
    ]
    with patch("shopify_client.requests.get", side_effect=responses), \
         patch("shopify_client.time.sleep"):  # don't actually sleep in tests
        orders = client.fetch_pending_orders()
    assert len(orders) == 1
