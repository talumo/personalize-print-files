import logging, time
import requests
from urllib.parse import urlencode
from models import Order, LineItem

logger = logging.getLogger(__name__)

PERSONALIZATION_KEYS = {"personalization", "personalization:", "personalization::", "personalisation", "name"}

# Maps lowercase piece keywords → canonical suffix appended to the product title
# so template keyword matching can identify the product type.
PIECE_MAP = {
    "placemat":        "Placemat",
    "plate":           "Plate",
    "bowl":            "Bowl",
    "mug":             "Mug",
    "fork & spoon":    "Spoon Fork",
    "fork and spoon":  "Spoon Fork",
    "spoon & fork":    "Spoon Fork",
    "spoon and fork":  "Spoon Fork",
    "fork spoon":      "Spoon Fork",
    "spoon fork":      "Spoon Fork",
}

# Property names that indicate an add-on fork & spoon (with/without trailing colon)
FORK_SPOON_PROP_KEYS = {
    "matching fork & spoon",
    "matching fork & spoon:",
    "matching fork and spoon",
    "matching fork and spoon:",
    "add matching fork & spoon",
    "add fork & spoon",
}


def _parse_pieces(combo_str: str) -> list:
    """Split 'Placemat + Plate + Bowl' into canonical piece names.

    Unknown tokens are kept as-is so template matching can still attempt them.
    """
    pieces = []
    for part in combo_str.split("+"):
        part = part.strip()
        lower = part.lower()
        matched = next((canonical for key, canonical in PIECE_MAP.items() if key in lower), None)
        if matched:
            pieces.append(matched)
        elif part:
            pieces.append(part)
    return pieces


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
        resp.raise_for_status()

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
            props = item.get("properties", [])
            name = self._extract_personalization(props)
            if not name:
                logger.warning(
                    "Order %s: line item %r has no personalization property",
                    raw.get("id"), item.get("title"),
                )
                continue

            pieces = self._extract_pieces(item, props)
            base_title = item["title"]

            if pieces:
                for piece in pieces:
                    items.append(LineItem(title=f"{base_title} {piece}", name=name))
            else:
                items.append(LineItem(title=base_title, name=name))

        return Order(
            order_id=str(raw["id"]),
            order_number=str(raw.get("order_number", "")),
            created_at=raw.get("created_at", ""),
            line_items=items,
        )

    def _extract_pieces(self, item: dict, props: list) -> list:
        """Return ordered list of piece names to generate, or [] for single items."""
        # variant_title holds the dropdown selection, e.g. "Placemat + Plate + Bowl + Mug"
        variant_title = (item.get("variant_title") or "").strip()
        skip_variants = {"default title", ""}

        if variant_title.lower() not in skip_variants:
            pieces = _parse_pieces(variant_title)
        else:
            # Fall back to checking if any property name looks like a combo
            pieces = []
            for prop in props:
                prop_name = prop.get("name", "")
                if "+" in prop_name:
                    pieces = _parse_pieces(prop_name)
                    break

        if not pieces:
            return []

        # Add fork & spoon if the add-on property is "Yes"
        if self._wants_fork_spoon(props) and "Spoon Fork" not in pieces:
            pieces.append("Spoon Fork")

        return pieces

    def _wants_fork_spoon(self, props: list) -> bool:
        for prop in props:
            key = prop.get("name", "").lower().strip()
            if key in FORK_SPOON_PROP_KEYS:
                return prop.get("value", "").lower().strip() in ("yes", "y", "true", "1")
        return False

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
