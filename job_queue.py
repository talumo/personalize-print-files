import json
import logging
import queue
import threading
import uuid
from datetime import datetime, timezone

import db
from shopify_client import ShopifyClient, ShopifyAuthError
from web_template_manager import WebTemplateManager
from file_generator import generate_order

logger = logging.getLogger(__name__)

_queue = queue.Queue()


def enqueue(order_ids: list) -> str:
    """Add order IDs to the job queue. Returns the job_id."""
    job_id = str(uuid.uuid4())
    db.create_job(job_id, order_ids, status='pending')
    _queue.put(job_id)
    logger.info("Enqueued job %s for orders: %s", job_id, order_ids)
    return job_id


def _process_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        logger.error("Job %s not found", job_id)
        return

    db.update_job_status(job_id, 'running')
    order_ids = json.loads(job['order_ids'])

    token = db.get_setting('shopify_access_token')
    if not token:
        logger.error("Job %s failed: Shopify access token not configured", job_id)
        db.update_job_status(job_id, 'failed', error='Shopify access token not configured. Complete setup in Settings.')
        return
    shop = db.get_setting('shopify_store', 'khd-kids.myshopify.com')
    version = db.get_setting('shopify_api_version', '2024-04')
    client = ShopifyClient(token, shop, version)
    tm = WebTemplateManager()
    config = db.get_web_config()

    total_gen = total_skip = total_fail = 0
    zip_paths = []

    for order_id in order_ids:
        try:
            orders = client.fetch_order_by_id(order_id)
            for order in orders:
                result = generate_order(order, tm, config)
                total_gen += result.files_generated
                total_skip += result.files_skipped
                total_fail += result.files_failed
                db.mark_processed(order_id, job_id)
                if result.zip_path:
                    zip_paths.append(result.zip_path)
                    logger.info("Order %s zip: %s", order_id, result.zip_path)
                else:
                    logger.warning("Order %s: no zip path returned — %d generated, %d failed",
                                   order_id, result.files_generated, result.files_failed)
        except ShopifyAuthError as e:
            logger.error("Auth error processing order %s: %s", order_id, e)
            db.update_job_status(job_id, 'failed', error='Shopify authentication failed. Check API credentials in Settings.')
            return  # Stop the whole job on auth failure
        except Exception as e:
            logger.error("Error processing order %s: %s", order_id, e)
            total_fail += 1

    result_json = json.dumps({
        'generated': total_gen,
        'skipped': total_skip,
        'failed': total_fail,
        'zip_paths': zip_paths,
        'order_count': len(order_ids),
    })
    db.update_job_status(job_id, 'complete', result_json=result_json)
    logger.info("Job %s complete: %s", job_id, result_json)


def _worker():
    while True:
        job_id = _queue.get()
        try:
            _process_job(job_id)
        except Exception as e:
            logger.exception("Unhandled error in job %s", job_id)
            db.update_job_status(job_id, 'failed', error=str(e))
        finally:
            _queue.task_done()


# Start background worker thread when module is imported
_worker_thread = threading.Thread(target=_worker, daemon=True, name='job-worker')
_worker_thread.start()
