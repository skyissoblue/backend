# Lanzhi Backend

澜知选股 App 的独立后端，包含 FastAPI 渐进式选股引擎、本地 A 股行情管道、MySQL 元数据、Redis 因子缓存和插件化 Alpha 因子系统。

## 目录

```text
factor_system/       # 206 个技术、Alpha、形态因子及预计算任务
selection_engine/    # 会话、中文解析、行情更新和 FastAPI API
Dockerfile
docker-compose.yml   # backend + MySQL + Redis
e2e_test.py
```

## Docker 启动

```bash
cp .env.example .env
# 修改 .env 中的 MySQL 密码
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

API 文档：`http://127.0.0.1:8000/docs`

服务数据保存在 Docker volumes 中，重新构建镜像不会清除 MySQL、Redis 或 Parquet K 线。

## 本地开发

```bash
python -m venv .venv
pip install -r requirements.txt
pytest -q
SELECTION_ENGINE_DATA_MODE=mock python e2e_test.py
```

要求 Python 3.10+，生产镜像使用 Python 3.11。

## 因子系统

```bash
docker compose exec backend python -m factor_system.main list
docker compose exec backend python -m factor_system.main run --kind alpha
docker compose exec backend python -m factor_system.main run --codes 000001,000002
docker compose exec backend python -m factor_system.main status
```

当前因子目录：150 个 TA-Lib 技术指标、23 个 Alpha101/191、33 个结构形态因子。行情任务更新一批本地 K 线后，会自动重算该批股票的因子。

通用因子筛选示例：

```json
{"type":"factor","name":"alpha_101","op":">","value":0.5}
```

查看因子目录：`GET /api/factors`。

## DeepSeek 条件解析

复杂自然语言条件使用 DeepSeek JSON Output 解析；常用中文条件优先由本地规则处理，即使模型服务不可用也能继续使用。配置项：

```env
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

## 主要 API

- `POST /api/session`
- `POST /api/session/{id}/condition`
- `POST /api/session/{id}/parse-and-apply`
- `DELETE /api/session/{id}/condition/last`
- `DELETE /api/session/{id}`
- `GET /api/session/{id}/stocks`
- `GET /api/session/{id}/conditions`
- `GET /api/factors`
