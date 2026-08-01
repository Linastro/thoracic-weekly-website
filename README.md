# 胸外文献每日监控站

> PubMed 每日抓取胸外文献 → LLM(MiniMax M3)分类与翻译 → SQLite 持久化 → Astro 静态网站展示。
> 类似 <https://aihot.virxact.com/all> 的医学文献版本。

## 当前状态(2026-08-01)

- 65 篇 publish articles(2026-07-20 ~ 2026-07-31)
- 本地 uvicorn :8080 + Astro dev :4321(无 Docker)

## 本地预览(无需 Docker,Phase A 开发模式)

```bash
# 1. 启动后端
PYTHONPATH=api/src DB_PATH=/tmp/thoracic-data/thoracic.db SNAPSHOT_DIR=/tmp/thoracic-data/snapshots \
  .venv/bin/uvicorn thoracic.main:app --host 0.0.0.0 --port 8080 &

# 2. 启动前端 dev(带 vite proxy)
cd web && npm run dev &

# 浏览器:http://localhost:4321
```

## 本地完整模拟(需 Docker Desktop,Phase A 模拟阶段)

适合"想看完整自动更新流程"的用户。

### 安装 Docker Desktop(macOS)

1. 打开 <https://www.docker.com/products/docker-desktop/>
2. 下载 Apple Silicon 版本
3. 安装后启动 Docker Desktop(菜单栏图标)
4. 验证:`docker --version` 与 `docker info | head -3`

### 启动

```bash
cd /Users/linastro/Documents/Claude\ Projects/Thoracic-Weekly-Server

# 构建所有镜像(api + cron,共享镜像)
docker compose build

# 启动 3 容器
docker compose up -d

# 查看日志
docker compose logs -f cron

# 健康检查
curl http://localhost:8080/api/health
```

cron 容器启动后会:

1. **entrypoint**:检查 `web_dist` 是否为空,空则跑一次 `npm run build` 让 nginx 有内容可服务
2. **`@reboot`**:立即 build Astro 网站(从 snapshot 读取最新数据)
3. **每日北京时间 8:00(= UTC 0:00)**:抓前一天 → LLM → SQLite → snapshot → `npm run build`
4. **每周一**:清理 180 天前 snapshot JSON
5. nginx 容器从 `web_dist` named volume 读取最新 dist

### 数据流(自动 rebuild)

```
cron container                        web container
┌──────────────────────┐              ┌──────────────┐
│ supercronic          │              │  nginx :80   │
│  ↓                  │              │  ↑           │
│  daily.py           │              │  reads       │
│   ↓                 │              │  web_dist    │
│  SQLite (thoracic-data)            │  (ro)        │
│   ↓                 │              │              │
│  snapshot JSON →   ─┼── web_dist ──┼─► 静态文件   │
│  npm run build      │  (volume)    │              │
│   ↓                 │              │              │
│  writes back to web_dist            │              │
└──────────────────────┘              └──────────────┘
```

## 部署到云服务器(Phase B)

Phase B 实施计划见 `PLAN.md`:

- `deploy.sh user@<server-ip>` 推送镜像 + 远端启动
- 服务器需 Ubuntu 22.04+ + Docker
- 配置 Caddy / nginx + Let's Encrypt 实现 HTTPS(可选)

## 关键文件

- 检索规则:`胸外科周报PubMed检索规则.md`
- 实施计划:`PLAN.md`
- 后端入口:`api/src/thoracic/main.py`
- 前端入口:`web/src/pages/index.astro`
- Docker 编排:`docker-compose.yml`
- cron 配置:`cron/crontab`
- 防污染过滤:`api/src/thoracic/pipeline/daily.py`(search "filtered {filtered_out}")
- snapshot 重建:`api/src/thoracic/scripts/rewrite_snapshots.py`
