import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get('DB_PATH', 'app.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS templates (
                theme_key        TEXT NOT NULL,
                product_key      TEXT NOT NULL,
                template_path    TEXT NOT NULL,
                text_box_json    TEXT NOT NULL,
                max_font_size    INTEGER DEFAULT 72,
                min_font_size    INTEGER DEFAULT 18,
                font_color       TEXT DEFAULT '#5A3E2B',
                letter_spacing   INTEGER DEFAULT 0,
                dpi              INTEGER DEFAULT 300,
                theme_keywords   TEXT DEFAULT '[]',
                product_keywords TEXT DEFAULT '[]',
                PRIMARY KEY (theme_key, product_key)
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id       TEXT PRIMARY KEY,
                order_ids    TEXT NOT NULL,
                status       TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                completed_at TEXT,
                result_json  TEXT
            );

            CREATE TABLE IF NOT EXISTS processed_orders (
                order_id     TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL,
                job_id       TEXT
            );
        """)
        conn.commit()
    finally:
        conn.close()


def reset_stale_jobs():
    """Set status='failed' for any jobs with status='running' (interrupted on restart)."""
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                completed_at = ?,
                result_json = ?
            WHERE status = 'running'
            """,
            (datetime.now(timezone.utc).isoformat(), json.dumps({'error': 'Server restarted during processing'})),
        )
        conn.commit()
    finally:
        conn.close()


# --- app_settings ---

def get_setting(key: str, default=None) -> str | None:
    conn = get_conn()
    try:
        row = conn.execute('SELECT value FROM app_settings WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str):
    conn = get_conn()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)',
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_settings() -> dict:
    conn = get_conn()
    try:
        rows = conn.execute('SELECT key, value FROM app_settings').fetchall()
        return {row['key']: row['value'] for row in rows}
    finally:
        conn.close()


# --- templates ---

def get_all_templates() -> list:
    conn = get_conn()
    try:
        rows = conn.execute('SELECT * FROM templates').fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_template(theme_key: str, product_key: str):
    conn = get_conn()
    try:
        row = conn.execute(
            'SELECT * FROM templates WHERE theme_key = ? AND product_key = ?',
            (theme_key, product_key),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_template(theme_key, product_key, template_path, text_box_json,
                    max_font_size, min_font_size, font_color, letter_spacing,
                    dpi, theme_keywords, product_keywords):
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO templates
                (theme_key, product_key, template_path, text_box_json,
                 max_font_size, min_font_size, font_color, letter_spacing,
                 dpi, theme_keywords, product_keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (theme_key, product_key, template_path, text_box_json,
             max_font_size, min_font_size, font_color, letter_spacing,
             dpi, theme_keywords, product_keywords),
        )
        conn.commit()
    finally:
        conn.close()


def delete_template(theme_key: str, product_key: str):
    conn = get_conn()
    try:
        conn.execute(
            'DELETE FROM templates WHERE theme_key = ? AND product_key = ?',
            (theme_key, product_key),
        )
        conn.commit()
    finally:
        conn.close()


def import_from_json(json_path: str) -> int:
    """Load template_config.json, insert all themes/products into templates table.

    Returns count of templates imported.
    """
    with open(json_path, 'r') as f:
        config = json.load(f)

    defaults = config.get('defaults', {})
    theme_mapping = config.get('theme_mapping', {})
    themes = config.get('themes', {})

    count = 0
    for theme_key, products in themes.items():
        # theme_keywords come from theme_mapping values for this theme_key
        theme_keywords = json.dumps(theme_mapping.get(theme_key, []))

        for product_key, product_data in products.items():
            template_path = product_data.get('template', '')
            text_box = product_data.get('text_box', {})
            text_box_json = json.dumps(text_box)

            max_font_size = product_data.get('max_font_size', defaults.get('max_font_size', 72))
            min_font_size = product_data.get('min_font_size', defaults.get('min_font_size', 18))
            font_color = product_data.get('font_color', defaults.get('font_color', '#5A3E2B'))
            letter_spacing = product_data.get('letter_spacing', defaults.get('letter_spacing', 0))
            dpi = product_data.get('dpi', defaults.get('dpi', 300))
            product_keywords = json.dumps(product_data.get('keywords', []))

            upsert_template(
                theme_key=theme_key,
                product_key=product_key,
                template_path=template_path,
                text_box_json=text_box_json,
                max_font_size=max_font_size,
                min_font_size=min_font_size,
                font_color=font_color,
                letter_spacing=letter_spacing,
                dpi=dpi,
                theme_keywords=theme_keywords,
                product_keywords=product_keywords,
            )
            count += 1

    return count


# --- jobs ---

def create_job(job_id: str, order_ids: list, status: str = 'pending'):
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO jobs (job_id, order_ids, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, json.dumps(order_ids), status,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: str):
    conn = get_conn()
    try:
        row = conn.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_jobs(limit: int = 50) -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            'SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?', (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_completed_jobs() -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = 'complete' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_job_status(job_id: str, status: str, result_json: str = None, error: str = None):
    conn = get_conn()
    try:
        completed_at = (
            datetime.now(timezone.utc).isoformat()
            if status in ('complete', 'failed')
            else None
        )

        if error is not None and result_json is None:
            result_json = json.dumps({'error': error})

        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                completed_at = ?,
                result_json = ?
            WHERE job_id = ?
            """,
            (status, completed_at, result_json, job_id),
        )
        conn.commit()
    finally:
        conn.close()


# --- processed_orders ---

def is_processed(order_id: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            'SELECT 1 FROM processed_orders WHERE order_id = ?', (order_id,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_processed(order_id: str, job_id: str = None):
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO processed_orders (order_id, processed_at, job_id)
            VALUES (?, ?, ?)
            """,
            (order_id, datetime.now(timezone.utc).isoformat(), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def unmark_processed(order_id: str):
    """Remove an order from processed_orders so it reappears on the Orders page."""
    conn = get_conn()
    try:
        conn.execute('DELETE FROM processed_orders WHERE order_id = ?', (order_id,))
        conn.commit()
    finally:
        conn.close()


def get_processed_order_ids() -> set:
    conn = get_conn()
    try:
        rows = conn.execute('SELECT order_id FROM processed_orders').fetchall()
        return {row['order_id'] for row in rows}
    finally:
        conn.close()


# --- config adapter for file_generator ---

@dataclass
class WebConfig:
    font_path: str
    output_dir: str


def get_web_config() -> WebConfig:
    return WebConfig(
        font_path=get_setting('font_path', ''),
        output_dir=get_setting('output_dir', 'output'),
    )
