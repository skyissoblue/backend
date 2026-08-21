# 渐进式选股核心引擎

引擎位于 `src/selection_engine`，使用固定随机种子生成 5,400 只模拟股票，支持逐步添加条件、撤销最后一步和重置全市场。

## 运行演示

```powershell
$env:PYTHONPATH = "src"
python -m selection_engine
```

## 运行测试

```powershell
python -m pip install -e ".[test]"
python -m pytest
```

## 使用示例

```python
from selection_engine import SelectionSession

session = SelectionSession()
result = session.apply_condition({"type": "ma_cross_weekly"})
result = session.apply_condition({"type": "rps", "op": ">", "value": 87})

print(result["before"], result["after"], result["removed"])
session.remove_last()
session.reset()
```

`stocks` 中每条记录包含：`code`、`name`、`industry`、`board`、`close`、`ma10_weekly`、`rps_250`、`volume_ratio`、`market_cap`、`pe` 和 `listed_days`。
