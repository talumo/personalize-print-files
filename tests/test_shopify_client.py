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

def _bundle_order(variant_title, props_extra=None):
    """Helper: one line item bundle order with given variant_title."""
    props = [{"name": "Personalization:", "value": "Tristan"}]
    if props_extra:
        props.extend(props_extra)
    return {
        "id": 2001,
        "order_number": "#2001",
        "created_at": "2026-03-31T10:00:00Z",
        "line_items": [{
            "title": "Airplane Kids Dinnerware",
            "variant_title": variant_title,
            "properties": props,
        }]
    }


def test_bundle_variant_expands_to_one_item_per_piece():
    client = make_client()
    order_data = _bundle_order("Placemat + Plate + Bowl + Mug")
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    titles = [li.title for li in orders[0].line_items]
    assert len(titles) == 4
    assert "Airplane Kids Dinnerware Placemat" in titles
    assert "Airplane Kids Dinnerware Plate" in titles
    assert "Airplane Kids Dinnerware Bowl" in titles
    assert "Airplane Kids Dinnerware Mug" in titles
    assert all(li.name == "Tristan" for li in orders[0].line_items)


def test_bundle_partial_set():
    client = make_client()
    order_data = _bundle_order("Placemat + Plate")
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    titles = [li.title for li in orders[0].line_items]
    assert len(titles) == 2
    assert "Airplane Kids Dinnerware Placemat" in titles
    assert "Airplane Kids Dinnerware Plate" in titles


def test_fork_spoon_addon_yes_appends_spoon_fork():
    client = make_client()
    order_data = _bundle_order(
        "Placemat + Plate + Bowl + Mug",
        props_extra=[{"name": "Matching fork & spoon:", "value": "Yes"}],
    )
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    titles = [li.title for li in orders[0].line_items]
    assert len(titles) == 5
    assert "Airplane Kids Dinnerware Spoon Fork" in titles


def test_fork_spoon_addon_no_does_not_append():
    client = make_client()
    order_data = _bundle_order(
        "Placemat + Plate",
        props_extra=[{"name": "Matching fork & spoon:", "value": "No"}],
    )
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    titles = [li.title for li in orders[0].line_items]
    assert len(titles) == 2
    assert not any("Spoon Fork" in t for t in titles)


def test_fork_spoon_standalone_variant():
    client = make_client()
    order_data = _bundle_order("Fork & Spoon")
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    titles = [li.title for li in orders[0].line_items]
    assert len(titles) == 1
    assert titles[0] == "Airplane Kids Dinnerware Spoon Fork"


def test_single_piece_variant():
    client = make_client()
    order_data = _bundle_order("Placemat")
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    titles = [li.title for li in orders[0].line_items]
    assert len(titles) == 1
    assert titles[0] == "Airplane Kids Dinnerware Placemat"


def test_default_title_variant_uses_product_title():
    """Products with no variant selection (Default Title) are not expanded."""
    client = make_client()
    order_data = _bundle_order("Default Title")
    with patch("shopify_client.requests.get",
               return_value=mock_response({"orders": [order_data]})):
        orders = client.fetch_pending_orders()
    assert len(orders[0].line_items) == 1
    assert orders[0].line_items[0].title == "Airplane Kids Dinnerware"


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
