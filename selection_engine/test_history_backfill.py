from pathlib import Path

import pandas as pd

from selection_engine import history_backfill


def _frame(rows: int = 60) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=rows)
    close = pd.Series(range(rows), dtype=float) + 10
    return pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000,
            "amount": 10000,
        }
    )


def test_full_history_backfill_is_resumable(monkeypatch, tmp_path: Path):
    state_file = tmp_path / "state.json"
    saved: list[str] = []
    snapshots: list[dict] = []
    monkeypatch.setattr(history_backfill, "STATE_FILE", state_file)
    monkeypatch.setattr(history_backfill, "HISTORY_WORKERS", 1)
    monkeypatch.setattr(history_backfill, "REQUEST_DELAY", 0)
    monkeypatch.setattr(history_backfill, "init_schema", lambda: None)
    monkeypatch.setattr(
        history_backfill,
        "load_stocks",
        lambda: [
            {"code": "000001", "name": "平安银行", "board": "主板"},
            {"code": "600000", "name": "浦发银行", "board": "主板"},
            {"code": "510300", "name": "沪深300ETF", "board": "ETF"},
        ],
    )
    monkeypatch.setattr(history_backfill.data_provider, "get_daily_kline", lambda code, start_date: _frame())
    monkeypatch.setattr(history_backfill.local_store, "save", lambda code, frame: saved.append(code))
    monkeypatch.setattr(history_backfill.local_store, "load", lambda code: _frame())
    monkeypatch.setattr(history_backfill, "upsert_stocks", lambda rows: snapshots.extend(rows))

    first = history_backfill.run(limit=1)
    second = history_backfill.run()

    assert first["succeeded"] == 1
    assert second["succeeded"] == 1
    assert set(saved) == {"000001", "600000"}
    assert all(item["listed_days"] == 60 for item in snapshots)
    assert {item["name"] for item in snapshots} == {"平安银行", "浦发银行"}
    assert "510300" not in saved
