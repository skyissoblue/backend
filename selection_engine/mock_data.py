"""生成确定且可复现的模拟 A 股数据。"""

from __future__ import annotations

import random
from typing import Any

Stock = dict[str, Any]
DEFAULT_MARKET_SIZE = 5_400
DEFAULT_SEED = 20260818


def generate_mock_market(size: int = DEFAULT_MARKET_SIZE, seed: int = DEFAULT_SEED) -> list[Stock]:
    """生成包含行情、估值和分类字段的模拟股票池。"""
    if size < 0:
        raise ValueError("size must be non-negative")

    rng = random.Random(seed)
    industries = ["科技", "医药", "消费", "金融", "新能源", "工业", "材料", "公用事业"]
    boards = ["主板", "创业板", "科创板", "北交所"]
    prefixes = ["华夏", "中科", "东方", "远景", "恒信", "金桥", "新锐", "天成"]
    suffixes = ["科技", "股份", "智造", "电子", "医药", "能源", "实业", "发展"]
    stocks: list[Stock] = []

    for index in range(size):
        ma10 = round(rng.uniform(5, 220), 2)
        stocks.append({
            "code": f"{index + 1:06d}",
            "name": f"{prefixes[index % 8]}{suffixes[(index // 8) % 8]}{index + 1}",
            "industry": industries[index % len(industries)],
            "board": boards[(index // len(industries)) % len(boards)],
            "close": round(ma10 * rng.uniform(0.72, 1.28), 2),
            "ma10_weekly": ma10,
            "rps_250": round(rng.uniform(0, 100), 2),
            "volume_ratio": round(rng.uniform(0.2, 5.0), 2),
            "market_cap": rng.randint(800_000_000, 300_000_000_000),
            "pe": round(rng.uniform(5, 150), 2),
            "listed_days": rng.randint(30, 8_000),
        })
    return stocks
