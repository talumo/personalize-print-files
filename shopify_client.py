import logging, time
import requests
from urllib.parse import urlencode, quote
from models import Order, LineItem

logger = logging.getLogger(__name__)

PERSONALIZATION_KEYS = {"personalization", "personalization::", "personalisation", "name"}

class ShopifyAuthError(Exception):
    pass

class ShopifyClient:
    def __init__(self, access_token: str, store: str, api_version: str):
        self._token = access_token
        self._store = store
        self._version = api_version
        self._headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    def _base_url(self):
        return f"https://{self._store}/admin/api/{self._version}"

    def _get(self, url, retries=3):
        delay = 2
        for attempt in range(retries + 1):
            resp = requests.get(url, headers=self._headers)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (401, 403):
                raise ShopifyAuthError(
                    f"Shopify auth failed ({resp.status_code}). "
                    "Check SHOPIFY_ACCESS_TOKEN and app permissions."
                )
            if resp.status_code == 429 and attempt < retries:
                logger.warning("Rate limited, retrying in %ds...", delay)
                time.sleep(delay)
                delay *= 2
                continue
            resp.raise_for_status()
        resp.raise_for_status()  # final attempt failed

    def fetch_pending_orders(self, since_date=None) -> list:
        params = {
            "financial_status": "paid",
            "fulfillment_status": "unfulfilled",
            "limit": 250,
        }
        if since_date:
            params["created_at_min"] = f"{since_date}T00:00:00Z"

        url = f"{self._base_url()}/orders.json?{urlencode(params)}"
        all_orders = []

        while url:
            resp = self._get(url)
            data = resp.json()
            for raw in data.get("orders", []):
                order = self._parse_order(raw)
                if order.line_items:
                    all_orders.append(order)
            # Pagination
            link = resp.headers.get("Link", "")
            url = self._next_url(link)

        return all_orders

    def fetch_order_by_id(self, order_id: str) -> list:
        url = f"{self._base_url()}/orders/{order_id}.json"
        resp = self._get(url)
        raw = resp.json().get("order", {})
        order = self._parse_order(raw)
        return [order] if order.line_items else []

    def _parse_order(self, raw: dict) -> Order:
        items = []
        for item in raw.get("line_items", []):
            name = self._extract_personalization(item.get("properties", []))
            if name:
                items.append(LineItem(title=item["title"], name=name))
            else:
                logger.warning(
                    "Order %s: line item %r has no personalization property",
                    raw.get("id"), item.get("title")
                )
        return Order(
            order_id=str(raw["id"]),
            order_number=str(raw.get("order_number", "")),
            created_at=raw.get("created_at", ""),
            line_items=items,
        )

    def _extract_personalization(self, properties: list):
        for prop in properties:
            if prop.get("name", "").lower() in PERSONALIZATION_KEYS:
                val = prop.get("value", "").strip()
                return val if val else None
        return None

    @staticmethod
    def _next_url(link_header: str):
        for part in link_header.split(","):
            if 'rel="next"' in part:
                return part.split(";")[0].strip().strip("<>")
        return None
