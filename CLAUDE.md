# CLAUDE.md

This file provides guidance to the AI agent when working with code in this repository.

PubMed 胸外文献每日监控站:PubMed 抓取 → LLM(当前 DeepSeek)分类翻译 → SQLite → snapshot JSON → Astro 静态站。三容器(api / cron / web)+ Caddy 前置 HTTPS。检索按 `[edat]`(PubMed 入库日),每日北京 14:00 跑。另有周报模式:每周一北京 19:00 用 DeepSeek 把上一周文献总结成按「病种 × 类型」的中文综述(见下「周报」)。站点已开源:https://github.com/Linastro/thoracic-weekly-website。

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

服务器 `~/thoracic-server` **是 git 仓库**(基线 `600346e`,见下「服务器版本管理与回退」节),靠 `scp` 同步文件。**web 源码、cron 脚本、crontab 都已 bind mount**(2026-08-06 起,见 docker-compose.yml),不再烤进镜像。

### 各层改动方式

| 改动对象 | 方式 |
|---|---|
| **web 源码**(`web/src`、`web/public` 等) | bind mount `./web:/app/web_src`。scp 到 `~/thoracic-server/web/` → 本机构建前端 → 上传产物(见下)。**无需重建镜像** |
| **cron 脚本/定时**(`cron/cron_jobs`、`cron/crontab`) | bind mount(`./cron/cron_jobs:/app/cron_jobs`、`./cron/crontab:/etc/crontab`)。scp 即可(注意 `chmod +x`);改 crontab 后需 `docker compose restart cron` 让 supercronic 重读 |
| **api Python 代码**(`api/src`) | 包装在镜像 site-packages,**必须 `docker compose build api` + `up -d --force-recreate api`**,`docker compose cp` 无效 |
| `nginx.conf` | 改它只需 `restart web` 的常驻 bind mount |
| `docker-compose.yml` | scp 后 `docker compose up -d --force-recreate`(不重建镜像,秒级) |
| `Caddyfile`(HTTPS/域名) | 新增 `caddy` 服务(Caddy 前置 nginx,自动 LE 证书)。改后 `scp Caddyfile` + `docker compose restart caddy` 重读,无需重建镜像 |

**前端发布(不在服务器上 build —— 1.6G 机器上 Astro build 会 OOM 卡死整机,已踩多次坑)**:

```bash
# 本机(Mac)构建:先确保 /tmp/thoracic-data/snapshots 有最新 snapshot(见"只重建前端")
cd web && npm run build && touch dist/.astro_build_ok
# 上传并灌进 web_dist 卷
scp -r web/dist root@<host>:/tmp/webdist
ssh root@<host> 'docker run --rm -v thoracic-server_web_dist:/app/web_dist -v /tmp/webdist:/dist:ro nginx:1.27-alpine sh -c "rm -rf /app/web_dist/* && cp -R /dist/. /app/web_dist/"'
```

> **改 web 源码必须同步到服务器 `~/thoracic-server/web/`**:daily.sh 每天 14:00 会用 bind mount 的**服务器端源码**重新 build 并覆盖 web_dist。只在本机构建上传产物、不同步源码,下次 daily 重建就会回退(2026-08-07 已踩坑:个人 logo/by/页面措辞全部回退)。改完源码先 scp/rsync 到服务器再重建前端。
>
> **绝不在服务器上跑 `docker compose build cron`**:npm install 与 api/web 抢内存 → 整机 swap 抖动 30+ 分钟、SSH 失联(2026-08-06 当天踩 3 次)。api 构建是 uv sync(非 npm),相对安全。
> **`docker compose cp` 进容器的改动只在可写层**,`up -d --force-recreate` 即丢失;bind mount 的改动则持久。

## 服务器版本管理与回退(2026-08-13 起)

服务器 `~/thoracic-server` **现在是 git 仓库**(基线 `600346e`),本地仓库仍是代码权威;两者互补 —— 本地 git 管代码演进,服务器 git 管"线上部署了什么"。本地仓库已开源并挂 `origin`(→ github.com/Linastro/thoracic-weekly-website),可正常 `git push`;服务器 git 则**绝不 push**(见红线)。改服务器前必走下面的节奏。

### 改动前:先打快照(一条命令留四个回退点)

```bash
ssh root@<host> 'cd ~/thoracic-server && ./backup.sh'
```

`backup.sh` 一次备份:DB(`/data/thoracic.db.bak-<stamp>`)、snapshots(`/data/snapshots-<stamp>.tar.gz`)、`.env`(`backups/env-<stamp>`)、api 镜像 tag(`thoracic-server-api:bak-<stamp>`)。

### 改动后:scp 完文件就留一个回退点

```bash
ssh root@<host> 'cd ~/thoracic-server && git add -A && git commit -m "改了啥(为什么)"'
```

### 回退方式(三层,工具不同)

| 层 | 内容 | 回退 |
|---|---|---|
| 文件(web 源码 / cron / nginx / compose) | 服务器 git | `git checkout <commit> -- <file>` 或 `git revert` |
| api 镜像(Python 代码) | 镜像 tag | `docker tag thoracic-server-api:bak-<stamp> thoracic-server-api:local` 后 `up -d --force-recreate api` |
| 数据(SQLite + snapshots) | 卷内 `.bak` | 停 api → 覆盖回 `.bak` → 起 api(流程见 HANDOFF §6.12) |

### 红线(违反即坏)

1. **绝不**把 `.env`、`web/node_modules/`、`*.bak` 提交进服务器 git(已由 `.gitignore` 排除;提交后 `git ls-files | grep -E '\.env$|node_modules|\.bak'` 必须为空)。
2. **绝不** `git push`(服务器连不上 github,且会泄露密钥)。
3. **绝不在服务器上 build**(`docker compose build` / `npm install` / `npm run build` 拖垮 1.6G 机器),见上文部署节。
4. 服务器 git 是 root 运行、文件属主是 UID 502(scp 遗留),报 "dubious ownership" 时已用 `git config --global --add safe.directory /root/thoracic-server` 豁免,勿删。

## 不能动的配置

| 位置 | 约束 |
|---|---|
| `docker-compose.yml` cron `init: true` | supercronic 一旦是 PID 1 就启用会崩的 reaper。别删,也别往镜像装 tini |
| `web_dist` volume `nocopy: true` | 否则 nginx 默认欢迎页被灌进产物目录 |
| `nginx.conf` `absolute_redirect off` | 否则目录补斜杠的 301 会按容器内 80 端口拼 origin,丢掉宿主映射端口 |
| `cron/crontab` | 容器 `TZ=Asia/Shanghai`,supercronic 按**北京时间**解释字段,不要按 UTC 换算。**已 bind mount**,改后 `restart cron` 即生效 |
| `api/Dockerfile` 里的 `sed ... tuna` | uv 下载源重写到清华 PyPI 镜像(`pypi.tuna.tsinghua.edu.cn`)。国内直连 `files.pythonhosted.org` 会随机挂起,重建 api 镜像曾卡死 10+ 分钟。**别删这行 sed**,否则下次 `docker compose build api` 又卡死 |
| api 环境变量 `THORACIC_METRICS_PATH` | 容器内包在 site-packages,相对路径找不到 `journal_metrics.json` |
| 服务器级配置(非 compose) | **`/etc/docker/daemon.json` 的 registry-mirrors(daocloud/1ms/proxy)与 2G swap(`/swapfile`+`/swapfile2`)在系统重置后会丢**,必须重建(见 HANDOFF §6.12) |
| `caddy_data` / `caddy_config` 卷 | Caddy 的 LE 证书 + ACME 账号持久化;删卷或 `down -v` 会重签证书、可能触发 LE 速率限制 |

## 数据流陷阱

- **前端只读 snapshot JSON**(`web/src/lib/data.ts`),不调 API,并按文章自身的 `epdat` 字段分组 —— 不是按文件名的日期。
- `write_daily_snapshot` 是**整文件覆盖**。任何重跑历史日期的代码都必须按 `epdat` 从 DB 重建(见 `pipeline/daily.py` step 6),否则会把该日已有文章从站点上抹掉。
- `run_backfill` 默认 `concurrency=3`,但每个 `run_daily` 各持独立 SQLite 连接。多日回填时若两天命中同一个 `epdat`,会同时重建同一个 JSON 且看不到对方未提交的行 → **多日调用一律传 `concurrency=1`**。
- 检索用 **`[edat]`**(PubMed 入库日):某入库日封口后永不再变,单日检索即完整,无需回看两天。`daily.sh` 在北京 14:00(= 美东凌晨,入库日翻页后)跑,`TARGET=$(TZ=America/New_York date -d yesterday)` = 前一个完整入库日。检索窗口与存储字段 `epdat`(同为入库日)一致。
- `articles` 表用 `llm_excluded`(0/1),**没有 `status` 列**。被排除的文章进 `excluded_records` 表,不进 `articles`。
- `daily_snapshots.article_count` 是**单次运行**统计,与 snapshot 文件篇数本就不一致,前端不用它。
- cron 容器**没有 Python**,`daily.sh` 通过 `curl` 调 `/api/backfill`(内部即 `run_daily`)。
- 健康检查是 `/api/health`(不是 `/healthz`)。

## 周报(LLM 每周综述)

每周一北京 19:00 `cron/cron_jobs/weekly.sh`(curl `POST /api/weekly` → `pipeline/weekly.py` 的 `run_weekly`)用 DeepSeek 把上一自然周(周一~周日,按 `articles.epdat` 区间)已入库文献总结成按「病种 × 类型」的中文综述(正文带 `[n]` 引用 + 底部英文参考文献),写 `SNAPSHOT_DIR/weekly/{start}-{end}.json`,再 `npm run build` 更新站点。

关键约束(踩坑后固化,别改回去):
- **LLM 按「病种 × 类型」逐类型各调一次**(`_summarize_disease`),不要合并成每病种一次 —— 大病种(肺癌 20+ 篇)单次调用输出会截断,退化成「罗列题名」兜底。
- **引用兜底在代码层保证**:`_ensure_citations`(空摘要→逐篇列题名带引用;无引用→末尾追加编号)+ `_collapse_citations`(相邻连续 `[1][2][3]` 折叠成 `[1-3]`);前端 `renderSummaryHtml` 把 `[n-m]` 整体链到首篇 `#ref-n`。
- 周报 JSON 放 `weekly/` **子目录**,别放 `SNAPSHOT_DIR` 顶层(否则 `data.ts` 的 `loadAllSnapshots` 会把它误当 daily 解析)。
- 服务器端 build 读 `/data/snapshots/weekly/`(cron 容器挂 `thoracic-data:/data`);改周报前端样式后要记得 scp 到服务器 `~/thoracic-server/web/`。

## 文件约定

- `HANDOFF.md` 已 gitignore,含服务器信息与完整踩坑记录 —— **接手前先读,永远不要 commit**。
- 一次性运维脚本放 `.scratch/`(已 gitignore),不要混进产品代码。
- 嵌套 ssh + `docker exec` + python 的引号极易出错(HTML 实体会漏进 SQL)。写成真实 `.py` 文件再 `scp` + `docker compose cp`,不要堆行内引号。
- 品牌素材:`web/public/*.png`(brand-wordmark / linastro-logo)是仓库根目录原图(未纳入 git,只在本机)的 `sips` 缩放版且已 commit。改品牌视觉需用户重新提供原图;改图后 `Sidebar.astro` 的 img `width/height` 要跟新比例同步(light/dark 比例可能不一致)。二维码同理:`web/public/qrcode-xiaohongshu.jpg`(作者页小红书)与 `qrcode-wechat.jpg`(项目简介页北医三院公众号)已 commit;根目录源图 `小红书二维码.jpg` / `北医三院胸外科公众号二维码.jpg` 未纳入 git 且 `.gitignore` 未覆盖。
- **ICP 备案号**:`Sidebar.astro` 底部 `.sidebar-footer` 里是 `京ICP备2026051313号`(法定要求,链接 beian.miit.gov.cn),别删。
