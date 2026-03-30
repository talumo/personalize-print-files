# tests/test_run_batch.py
import sys
from unittest.mock import patch, MagicMock
from models import Order, LineItem, GenerationResult

def _make_order(order_id="1001", name="Emma"):
    return Order(
        order_id=order_id, order_number=f"#{order_id}",
        created_at="2026-03-25T10:00:00Z",
        line_items=[LineItem(title="Bunny Love Plate Set", name=name)]
    )

def test_dry_run_prints_orders_without_generating(capsys):
    with patch("run_batch.load_config") as mock_cfg, \
         patch("run_batch.TemplateManager"), \
         patch("run_batch.ShopifyClient") as mock_client_cls, \
         patch("run_batch.StateManager") as mock_state_cls:

        mock_cfg.return_value = MagicMock(output_dir="/tmp/out")
        mock_client = MagicMock()
        mock_client.fetch_pending_orders.return_value = [_make_order()]
        mock_client_cls.return_value = mock_client
        mock_state = MagicMock()
        mock_state.is_processed.return_value = False
        mock_state_cls.return_value = mock_state

        import run_batch
        run_batch.main(["--dry-run"])

    out = capsys.readouterr().out
    assert "1" in out  # 1 order found
    mock_state.mark_processed.assert_not_called()

def test_already_processed_orders_are_skipped(capsys):
    with patch("run_batch.load_config") as mock_cfg, \
         patch("run_batch.TemplateManager"), \
         patch("run_batch.ShopifyClient") as mock_client_cls, \
         patch("run_batch.StateManager") as mock_state_cls, \
         patch("run_batch.generate_order") as mock_gen:

        mock_cfg.return_value = MagicMock(output_dir="/tmp/out")
        mock_client = MagicMock()
        mock_client.fetch_pending_orders.return_value = [_make_order()]
        mock_client_cls.return_value = mock_client
        mock_state = MagicMock()
        mock_state.is_processed.return_value = True   # already done
        mock_state_cls.return_value = mock_state

        import run_batch
        run_batch.main([])

    mock_gen.assert_not_called()

def test_order_flag_uses_targeted_fetch():
    with patch("run_batch.load_config") as mock_cfg, \
         patch("run_batch.TemplateManager"), \
         patch("run_batch.ShopifyClient") as mock_client_cls, \
         patch("run_batch.StateManager"), \
         patch("run_batch.generate_order") as mock_gen:

        mock_cfg.return_value = MagicMock(output_dir="/tmp/out")
        mock_client = MagicMock()
        mock_client.fetch_order_by_id.return_value = [_make_order("9999")]
        mock_client_cls.return_value = mock_client
        mock_gen.return_value = GenerationResult("9999", 1, 0, 0)

        import run_batch
        run_batch.main(["--order", "9999"])

    mock_client.fetch_order_by_id.assert_called_once_with("9999")
    mock_client.fetch_pending_orders.assert_not_called()

def test_failed_files_exits_with_code_1():
    with patch("run_batch.load_config") as mock_cfg, \
         patch("run_batch.TemplateManager"), \
         patch("run_batch.ShopifyClient") as mock_client_cls, \
         patch("run_batch.StateManager") as mock_state_cls, \
         patch("run_batch.generate_order") as mock_gen:

        mock_cfg.return_value = MagicMock(output_dir="/tmp/out")
        mock_client = MagicMock()
        mock_client.fetch_pending_orders.return_value = [_make_order()]
        mock_client_cls.return_value = mock_client
        mock_state = MagicMock()
        mock_state.is_processed.return_value = False
        mock_state_cls.return_value = mock_state
        mock_gen.return_value = GenerationResult("1001", 0, 0, 1)  # 1 failed

        import run_batch
        import pytest
        with pytest.raises(SystemExit) as exc:
            run_batch.main([])
        assert exc.value.code == 1
