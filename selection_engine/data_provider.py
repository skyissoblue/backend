"""Real A-share data access backed by AkShare."""
from __future__ import annotations
from datetime import date, timedelta
import time
from typing import Any
import pandas as pd

def _akshare():
    import akshare as ak
    return ak

def _retry(call, attempts: int = 3):
    last_error = None
    for attempt in range(attempts):
        try:
            return call()
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise last_error


def get_all_stocks() -> pd.DataFrame:
    raw = _retry(lambda: _akshare().stock_info_a_code_name())
    frame = raw.rename(columns={"代码": "code", "名称": "name"})
    if not {"code", "name"}.issubset(frame.columns):
        raise ValueError("AkShare stock list is missing code/name columns")
    result = frame.loc[:, ["code", "name"]].copy()
    result["code"] = result["code"].astype(str).str.strip().str.zfill(6)
    result["name"] = result["name"].astype(str).str.strip()
    return result.drop_duplicates("code").reset_index(drop=True)

def get_daily_kline(code: str, start_date: date | None = None) -> pd.DataFrame:
    end = date.today()
    start = start_date or (end - timedelta(days=550))
    normalized = str(code).zfill(6)
    try:
        raw = _retry(lambda: _akshare().stock_zh_a_hist(symbol=normalized, period="daily", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="qfq"))
    except Exception:
        exchange = "sh" if normalized.startswith(("5", "6", "9")) else "bj" if normalized.startswith(("4", "8")) else "sz"
        raw = _retry(lambda: _akshare().stock_zh_a_daily(symbol=f"{exchange}{normalized}", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"), adjust="qfq"))
    frame = raw.rename(columns={"日期":"date", "开盘":"open", "最高":"high", "最低":"low", "收盘":"close", "成交量":"volume", "成交额":"amount"})
    if "amount" not in frame.columns and {"close", "volume"}.issubset(frame.columns):
        frame["amount"] = pd.to_numeric(frame["close"], errors="coerce") * pd.to_numeric(frame["volume"], errors="coerce")
    required = ["date", "open", "high", "low", "close", "volume", "amount"]
    if not set(required).issubset(frame.columns):
        raise ValueError(f"AkShare kline for {code} is missing required columns")
    result = frame.loc[:, required].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    for column in required[1:]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=required).sort_values("date").reset_index(drop=True)

def _board_for_code(code: str) -> str:
    if code.startswith(("300", "301")): return "创业板"
    if code.startswith(("688", "689")): return "科创板"
    if code.startswith(("4", "8", "92")): return "北交所"
    return "主板"

def _number(value: Any) -> float | None:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(number) else float(number)

def get_stock_info(code: str) -> dict[str, Any]:
    normalized = str(code).zfill(6)
    raw = _retry(lambda: _akshare().stock_individual_info_em(symbol=normalized))
    if not {"item", "value"}.issubset(raw.columns):
        raise ValueError(f"AkShare stock info for {code} is missing item/value columns")
    values = dict(zip(raw["item"].astype(str), raw["value"], strict=False))
    return {"code":normalized, "name":str(values.get("股票简称", "")), "industry":str(values.get("行业", "")), "board":_board_for_code(normalized), "market_cap":_number(values.get("总市值")), "pe":_number(values.get("市盈率(TTM)", values.get("市盈率(静)")))}


def get_market_snapshot() -> pd.DataFrame:
    """Fetch one bulk quote snapshot for valuation fields."""
    raw = _retry(lambda: _akshare().stock_zh_a_spot_em())
    frame = raw.rename(columns={"代码": "code", "名称": "name", "最新价": "close", "总市值": "market_cap", "市盈率-动态": "pe"})
    columns = [column for column in ("code", "name", "close", "market_cap", "pe") if column in frame.columns]
    result = frame.loc[:, columns].copy()
    result["code"] = result["code"].astype(str).str.zfill(6)
    for column in ("close", "market_cap", "pe"):
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.drop_duplicates("code")
