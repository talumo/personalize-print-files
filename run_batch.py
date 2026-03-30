import argparse, sys, logging
from config import load_config
from shopify_client import ShopifyClient
from template_manager import TemplateManager, ConfigError
from file_generator import generate_order
from state_manager import StateManager

logger = logging.getLogger(__name__)

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate print-ready PDFs for personalized Shopify tableware orders."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show orders that would be processed without generating files")
    parser.add_argument("--order", metavar="ID",
                        help="Process a single order by ID (bypasses state check)")
    parser.add_argument("--since", metavar="DATE",
                        help="Only fetch orders on/after this UTC date (YYYY-MM-DD)")
    args = parser.parse_args(argv)

    config = load_config()

    try:
        tm = TemplateManager("template_config.json")
    except ConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    client = ShopifyClient(
        access_token=config.shopify_access_token,
        store=config.shopify_store,
        api_version=config.shopify_api_version,
    )
    state = StateManager("processed_orders.json")

    # Fetch orders
    if args.order:
        orders = client.fetch_order_by_id(args.order)
    else:
        orders = client.fetch_pending_orders(since_date=args.since)

    # Filter already-processed (unless --order forces reprocess)
    if not args.order:
        pending = [o for o in orders if not state.is_processed(o.order_id)]
    else:
        pending = orders

    if args.dry_run:
        print(f"Dry run: {len(pending)} order(s) would be processed")
        for o in pending:
            names = {i.name for i in o.line_items}
            print(f"  Order {o.order_number}: {len(o.line_items)} item(s), name(s): {names}")
        return

    orders_done = total_gen = total_skip = total_fail = 0
    for order in pending:
        result = generate_order(order, tm, config)
        state.mark_processed(order.order_id)
        orders_done += 1
        total_gen += result.files_generated
        total_skip += result.files_skipped
        total_fail += result.files_failed
        logger.info("Order %s: %d generated, %d skipped, %d failed",
                    order.order_id, result.files_generated,
                    result.files_skipped, result.files_failed)

    print(f"Done: {orders_done} order(s), "
          f"{total_gen} file(s) generated, "
          f"{total_skip} skipped, "
          f"{total_fail} failed")

    if total_fail > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
