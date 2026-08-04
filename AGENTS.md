# AGENTS.md

This file provides guidance to the AI agent when working with code in this repository.

PubMed 胸外文献每日监控站:PubMed 抓取 → MiniMax LLM 分类翻译 → SQLite → snapshot JSON → Astro 静态站。三容器(api / cron / web)。

## 语言约定

代码注释、commit message、文档一律用中文。commit 用 conventional commits 前缀(`fix(cron):`),正文写**为什么**而非改了什么。

## 本地运行

```bash
# 后端(必须显式给 PYTHONPATH 与两个路径变量,否则读不到包和数据)
PYTHONPATH=api/src DB_PATH=/tmp/thoracic-data/thoracic.db SNAPSHOT_DIR=/tmp/thoracic-data/snapshots \
  .venv/bin/uvicorn thoracic.main:app --port 8080

cd web && npm run dev      # :4321
cd web && npm run check    # astro check(唯一的类型检查)
```

**本仓库没有任何测试文件**。`web/package.json` 配了 vitest 但零测试,`api/` 下也没有。不要声称测试通过。

`pyproject.toml` 是 uv workspace:承载 `thoracic` 包的是**根项目 `thoracic-server`**(`where = ["api/src"]`),`api/` 只是 workspace 成员。改 Python 代码后重建镜像必须带 `--reinstall-package thoracic-server`(已写在 `api/Dockerfile`,**别删**),否则 uv 复用缓存 wheel,源码改动静默不生效。

## 部署(非常规,容易出错)

服务器 `~/thoracic-server` **不是 git 仓库**,靠 `scp` 同步文件。

`web/`、`cron/crontab`、`cron/cron_jobs/` 都**烤进 cron 镜像**(`COPY`),不是 bind mount。改这些之后:

```bash
scp <改动文件> root@<host>:~/thoracic-server/<同路径>
ssh root@<host> 'cd ~/thoracic-server && docker compose build cron && docker compose up -d cron'
# 前端还需显式重建产物到 web_dist volume:
ssh root@<host> 'cd ~/thoracic-server && docker compose exec -T cron sh -c \
  "cd /app/web_src && npm run build && cp -R dist/. /app/web_dist/"'
```

漏掉 `build cron` 会出现"文件传上去了但线上没变"。`docker compose cp`/`exec` 的改动只在容器可写层,`up -d --force-recreate` 即丢失。

`nginx.conf` 是唯一的 bind mount,改它只需 `restart web`。

## 不能动的配置

| 位置 | 约束 |
|---|---|
| `docker-compose.yml` cron `init: true` | supercronic 一旦是 PID 1 就启用会崩的 reaper。别删,也别往镜像装 tini |
| `web_dist` volume `nocopy: true` | 否则 nginx 默认欢迎页被灌进产物目录 |
| `nginx.conf` `absolute_redirect off` | 否则目录补斜杠的 301 会按容器内 80 端口拼 origin,丢掉宿主映射端口 |
| `cron/crontab` | 容器 `TZ=Asia/Shanghai`,supercronic 按**北京时间**解释字段,不要按 UTC 换算 |
| api 环境变量 `THORACIC_METRICS_PATH` | 容器内包在 site-packages,相对路径找不到 `journal_metrics.json` |

## 数据流陷阱

- **前端只读 snapshot JSON**(`web/src/lib/data.ts`),不调 API,并按文章自身的 `epdat` 字段分组 —— 不是按文件名的日期。
- `write_daily_snapshot` 是**整文件覆盖**。任何重跑历史日期的代码都必须按 `epdat` 从 DB 重建(见 `pipeline/daily.py` step 6),否则会把该日已有文章从站点上抹掉。
- `run_backfill` 默认 `concurrency=3`,但每个 `run_daily` 各持独立 SQLite 连接。多日回填时若两天命中同一个 `epdat`,会同时重建同一个 JSON 且看不到对方未提交的行 → **多日调用一律传 `concurrency=1`**。
- PubMed `[epdat]` 检索命中的文章,其 XML 里的 `epdat` 可能是别的日期;同一天不同时刻重跑返回的 PMID 也不同(索引陆续生成),所以 `daily.sh` 回看两天。
- `articles` 表用 `llm_excluded`(0/1),**没有 `status` 列**。被排除的文章进 `excluded_records` 表,不进 `articles`。
- `daily_snapshots.article_count` 是**单次运行**统计,与 snapshot 文件篇数本就不一致,前端不用它。
- cron 容器**没有 Python**,`daily.sh` 通过 `curl` 调 `/api/backfill`(内部即 `run_daily`)。
- 健康检查是 `/api/health`(不是 `/healthz`)。

## 文件约定

- `HANDOFF.md` 已 gitignore,含服务器信息与完整踩坑记录 —— **接手前先读,永远不要 commit**。
- 一次性运维脚本放 `.scratch/`(已 gitignore),不要混进产品代码。
- 嵌套 ssh + `docker exec` + python 的引号极易出错(HTML 实体会漏进 SQL)。写成真实 `.py` 文件再 `scp` + `docker compose cp`,不要堆行内引号。
