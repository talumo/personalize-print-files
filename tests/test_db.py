"""Tests for db.py — Flask scaffold + SQLite database layer."""
import json
import sqlite3

import pytest


# ---------------------------------------------------------------------------
# Fixture: redirect DB_PATH to a temp file so tests never touch app.db
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / 'test_app.db')
    monkeypatch.setenv('DB_PATH', db_file)
    # db module reads DB_PATH at import time via module-level variable;
    # patch the module attribute directly so every call uses the temp path.
    import db
    monkeypatch.setattr(db, 'DB_PATH', db_file)
    db.init_db()
    yield db_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _table_names(db_path: str) -> set:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

def test_init_db_creates_all_tables(isolated_db):
    tables = _table_names(isolated_db)
    assert 'app_settings' in tables
    assert 'templates' in tables
    assert 'jobs' in tables
    assert 'processed_orders' in tables


def test_init_db_is_idempotent(isolated_db):
    """Calling init_db() a second time must not raise."""
    import db
    db.init_db()
    tables = _table_names(isolated_db)
    assert len(tables) >= 4


# ---------------------------------------------------------------------------
# app_settings
# ---------------------------------------------------------------------------

def test_get_setting_returns_default_when_missing():
    import db
    assert db.get_setting('nonexistent') is None
    assert db.get_setting('nonexistent', 'fallback') == 'fallback'


def test_set_and_get_setting_round_trip():
    import db
    db.set_setting('font_path', '/fonts/test.ttf')
    assert db.get_setting('font_path') == '/fonts/test.ttf'


def test_set_setting_upserts():
    import db
    db.set_setting('output_dir', 'v1')
    db.set_setting('output_dir', 'v2')
    assert db.get_setting('output_dir') == 'v2'


def test_get_all_settings_returns_dict():
    import db
    db.set_setting('k1', 'v1')
    db.set_setting('k2', 'v2')
    settings = db.get_all_settings()
    assert isinstance(settings, dict)
    assert settings['k1'] == 'v1'
    assert settings['k2'] == 'v2'


def test_get_all_settings_empty():
    import db
    assert db.get_all_settings() == {}


# ---------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------

def test_create_and_get_job_round_trip():
    import db
    db.create_job('job-001', ['order-1', 'order-2'])
    row = db.get_job('job-001')
    assert row is not None
    assert row['job_id'] == 'job-001'
    assert row['status'] == 'pending'
    assert json.loads(row['order_ids']) == ['order-1', 'order-2']
    assert row['completed_at'] is None
    assert row['result_json'] is None


def test_create_job_custom_status():
    import db
    db.create_job('job-002', ['order-3'], status='running')
    row = db.get_job('job-002')
    assert row['status'] == 'running'


def test_get_job_returns_none_for_missing():
    import db
    assert db.get_job('does-not-exist') is None


def test_update_job_status_to_complete():
    import db
    db.create_job('job-003', ['order-4'])
    db.update_job_status('job-003', 'complete', result_json='{"files": ["a.pdf"]}')
    row = db.get_job('job-003')
    assert row['status'] == 'complete'
    assert row['completed_at'] is not None
    assert json.loads(row['result_json']) == {'files': ['a.pdf']}


def test_update_job_status_to_failed_with_error():
    import db
    db.create_job('job-004', ['order-5'])
    db.update_job_status('job-004', 'failed', error='Something went wrong')
    row = db.get_job('job-004')
    assert row['status'] == 'failed'
    assert row['completed_at'] is not None
    assert json.loads(row['result_json']) == {'error': 'Something went wrong'}


def test_update_job_status_running_no_completed_at():
    import db
    db.create_job('job-005', ['order-6'])
    db.update_job_status('job-005', 'running')
    row = db.get_job('job-005')
    assert row['status'] == 'running'
    assert row['completed_at'] is None


def test_get_all_jobs_ordered_and_limited():
    import db
    for i in range(5):
        db.create_job(f'job-bulk-{i}', [f'order-{i}'])
    jobs = db.get_all_jobs(limit=3)
    assert len(jobs) == 3


def test_get_completed_jobs():
    import db
    db.create_job('job-c1', ['o1'])
    db.create_job('job-c2', ['o2'])
    db.update_job_status('job-c1', 'complete')
    completed = db.get_completed_jobs()
    ids = [r['job_id'] for r in completed]
    assert 'job-c1' in ids
    assert 'job-c2' not in ids


# ---------------------------------------------------------------------------
# processed_orders
# ---------------------------------------------------------------------------

def test_mark_and_is_processed_round_trip():
    import db
    assert db.is_processed('order-X') is False
    db.mark_processed('order-X', job_id='job-Z')
    assert db.is_processed('order-X') is True


def test_mark_processed_without_job_id():
    import db
    db.mark_processed('order-Y')
    assert db.is_processed('order-Y') is True


def test_mark_processed_idempotent():
    """INSERT OR IGNORE — calling twice must not raise."""
    import db
    db.mark_processed('order-W')
    db.mark_processed('order-W')  # second call should not raise
    assert db.is_processed('order-W') is True


def test_get_processed_order_ids_returns_set():
    import db
    db.mark_processed('a1')
    db.mark_processed('a2')
    ids = db.get_processed_order_ids()
    assert isinstance(ids, set)
    assert 'a1' in ids
    assert 'a2' in ids


# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------

def _make_template(theme='floral', product='tote', **overrides):
    defaults = dict(
        theme_key=theme,
        product_key=product,
        template_path='templates/floral_tote.png',
        text_box_json='{"x": 10, "y": 20, "width": 100, "height": 50}',
        max_font_size=72,
        min_font_size=18,
        font_color='#5A3E2B',
        letter_spacing=0,
        dpi=300,
        theme_keywords='["floral", "garden"]',
        product_keywords='["tote", "bag"]',
    )
    defaults.update(overrides)
    return defaults


def test_upsert_and_get_template_round_trip():
    import db
    kw = _make_template()
    db.upsert_template(**kw)
    row = db.get_template('floral', 'tote')
    assert row is not None
    assert row['theme_key'] == 'floral'
    assert row['product_key'] == 'tote'
    assert row['font_color'] == '#5A3E2B'
    assert row['dpi'] == 300


def test_upsert_template_replaces_existing():
    import db
    db.upsert_template(**_make_template(font_color='#000000'))
    db.upsert_template(**_make_template(font_color='#FFFFFF'))
    row = db.get_template('floral', 'tote')
    assert row['font_color'] == '#FFFFFF'


def test_get_template_returns_none_for_missing():
    import db
    assert db.get_template('no-theme', 'no-product') is None


def test_get_all_templates():
    import db
    db.upsert_template(**_make_template('floral', 'tote'))
    db.upsert_template(**_make_template('stripe', 'mug'))
    rows = db.get_all_templates()
    assert len(rows) == 2


def test_delete_template():
    import db
    db.upsert_template(**_make_template())
    db.delete_template('floral', 'tote')
    assert db.get_template('floral', 'tote') is None


def test_delete_template_nonexistent_is_silent():
    import db
    db.delete_template('ghost', 'ghost')  # must not raise


# ---------------------------------------------------------------------------
# reset_stale_jobs
# ---------------------------------------------------------------------------

def test_reset_stale_jobs_marks_running_as_failed():
    import db
    db.create_job('stale-1', ['o1'], status='running')
    db.create_job('stale-2', ['o2'], status='running')
    db.create_job('ok-1', ['o3'], status='pending')
    db.create_job('ok-2', ['o4'], status='complete')

    db.reset_stale_jobs()

    assert db.get_job('stale-1')['status'] == 'failed'
    assert db.get_job('stale-2')['status'] == 'failed'
    # Non-running jobs must be untouched
    assert db.get_job('ok-1')['status'] == 'pending'
    assert db.get_job('ok-2')['status'] == 'complete'


def test_reset_stale_jobs_sets_error_result():
    import db
    db.create_job('stale-3', ['o5'], status='running')
    db.reset_stale_jobs()
    row = db.get_job('stale-3')
    result = json.loads(row['result_json'])
    assert 'error' in result
    assert result['error'] == 'Server restarted during processing'
    assert row['completed_at'] is not None


def test_reset_stale_jobs_no_running_jobs_is_noop():
    import db
    db.create_job('quiet-1', ['o6'], status='pending')
    db.reset_stale_jobs()  # must not raise
    assert db.get_job('quiet-1')['status'] == 'pending'
