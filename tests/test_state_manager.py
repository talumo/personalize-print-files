# tests/test_state_manager.py
import json, pytest
from pathlib import Path
from state_manager import StateManager

def test_new_state_file_created(tmp_path):
    sm = StateManager(tmp_path / "state.json")
    assert not sm.is_processed("1001")

def test_mark_and_check(tmp_path):
    sm = StateManager(tmp_path / "state.json")
    sm.mark_processed("1001")
    assert sm.is_processed("1001")
    assert not sm.is_processed("1002")

def test_state_persists_across_instances(tmp_path):
    path = tmp_path / "state.json"
    sm1 = StateManager(path)
    sm1.mark_processed("1001")
    sm2 = StateManager(path)
    assert sm2.is_processed("1001")

def test_corrupt_state_file_recovers(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("NOT VALID JSON")
    sm = StateManager(path)   # should not raise
    assert not sm.is_processed("1001")

def test_multiple_orders(tmp_path):
    sm = StateManager(tmp_path / "state.json")
    for oid in ["1", "2", "3"]:
        sm.mark_processed(oid)
    assert sm.is_processed("2")
    assert not sm.is_processed("4")
