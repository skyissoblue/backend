from types import SimpleNamespace
import pandas as pd
import pytest
from selection_engine import data_provider, indicators
from selection_engine.cache import MemoryCache
from selection_engine.session import SelectionSession

class FakeAkShare:
    def __init__(self): self.hist_calls = 0
    def stock_info_a_code_name(self): return pd.DataFrame({"code":["000001","300001","688001","800001"], "name":["科技一","医药二","科技三","消费四"]})
    def stock_zh_a_hist(self, **kwargs):
        self.hist_calls += 1
        code = kwargs["symbol"]
        dates = pd.bdate_range("2025-01-01", periods=260)
        base = {"000001":10, "300001":20, "688001":30, "800001":40}[code]
        step = {"000001":0.08, "300001":-0.02, "688001":0.15, "800001":0.01}[code]
        close = [base + step*i for i in range(260)]
        return pd.DataFrame({"日期":dates, "开盘":close, "最高":[x+1 for x in close], "最低":[x-1 for x in close], "收盘":close, "成交量":[100+i%5*20 for i in range(260)], "成交额":[100000+i for i in range(260)]})
    def stock_individual_info_em(self, symbol):
        industry = "科技" if symbol in {"000001","688001"} else "其他"
        return pd.DataFrame({"item":["股票简称","行业","总市值","市盈率(TTM)"], "value":[f"股票{symbol}",industry,int(symbol[-1] or 1)*10_000_000_000,20.5]})

@pytest.fixture
def fake_ak(monkeypatch):
    fake = FakeAkShare()
    monkeypatch.setattr(data_provider, "_akshare", lambda: fake)
    return fake

def test_get_all_stocks_uses_akshare(fake_ak):
    result = data_provider.get_all_stocks()
    assert list(result.columns) == ["code", "name"]
    assert result.iloc[1].to_dict() == {"code":"300001", "name":"医药二"}

def test_get_daily_kline_normalizes_columns(fake_ak):
    result = data_provider.get_daily_kline("000001")
    assert list(result.columns) == ["date","open","high","low","close","volume","amount"]
    assert pd.api.types.is_datetime64_any_dtype(result["date"])

def test_get_stock_info(fake_ak):
    info = data_provider.get_stock_info("688001")
    assert info["industry"] == "科技" and info["board"] == "科创板"
    assert info["market_cap"] == 10_000_000_000 and info["pe"] == 20.5

def test_indicators(fake_ak):
    frame = data_provider.get_daily_kline("000001")
    assert indicators.calc_weekly_ma10(frame) > 0
    assert indicators.calc_volume_ratio(frame) > 0
    assert isinstance(indicators.calc_ma_deviation_weekly(frame), float)

def test_rps_ranks_whole_market():
    closes = {"A":pd.Series([10,20]), "B":pd.Series([10,15]), "C":pd.Series([10,9])}
    assert indicators.calc_rps_250("A", closes) == 100.0
    assert indicators.calc_rps_250("B", closes) == pytest.approx(200/3)

def test_cache_only_calculates_once():
    calls = SimpleNamespace(count=0)
    def calculate(value): calls.count += 1; return value*2
    cache = MemoryCache()
    assert cache.get_or_calc("000001", calculate, 3) == 6
    assert cache.get_or_calc("000001", calculate, 99) == 6
    assert calls.count == 1

@pytest.mark.parametrize("condition", [
    {"type":"industry", "value":"科技"}, {"type":"board", "value":"创业板"},
    {"type":"ma_cross_weekly"}, {"type":"ma_deviation_weekly", "max_pct":10},
    {"type":"rps", "op":">", "value":50}, {"type":"volume_ratio", "op":">", "value":0.5},
    {"type":"market_cap", "op":"<", "value":50_000_000_000},
])
def test_each_condition_with_mocked_akshare(fake_ak, condition):
    result = SelectionSession().apply_condition(condition)
    assert result["before"] == 4 and 0 <= result["after"] <= 4

def test_conditions_stack_and_undo(fake_ak):
    session = SelectionSession()
    first = session.apply_condition({"type":"industry", "value":"科技"})
    second = session.apply_condition({"type":"ma_cross_weekly"})
    assert second["before"] == first["after"]
    undone = session.remove_last()
    assert undone["stocks"] == first["stocks"]

def test_market_data_is_cached(fake_ak):
    session = SelectionSession(limit=1)
    session.apply_condition({"type":"ma_cross_weekly"})
    session.remove_last(); session.apply_condition({"type":"ma_cross_weekly"})
    assert fake_ak.hist_calls == 1


def test_local_mode_never_calls_akshare(monkeypatch):
    local_stocks = [{
        "code": "000001", "name": "本地科技", "industry": "科技", "board": "主板",
        "close": 12.0, "weekly_ma10": 10.0, "weekly_deviation": 2.0,
        "rps_250": 90.0, "volume_ratio": 2.0, "market_cap": 10_000_000_000,
        "pe": 18.0, "listed_days": 1000,
    }]
    monkeypatch.setenv("SELECTION_ENGINE_DATA_MODE", "local")
    monkeypatch.setattr("selection_engine.database.load_stocks", lambda limit=None: local_stocks)
    monkeypatch.setattr(data_provider, "get_all_stocks", lambda: pytest.fail("AkShare must not be called"))
    monkeypatch.setattr(data_provider, "get_stock_info", lambda code: pytest.fail("AkShare must not be called"))
    monkeypatch.setattr(data_provider, "get_daily_kline", lambda code: pytest.fail("AkShare must not be called"))

    session = SelectionSession()
    result = session.apply_condition({"type": "industry", "value": "科技"})
    assert result["after"] == 1
    assert session.apply_condition({"type": "ma_cross_weekly"})["after"] == 1
