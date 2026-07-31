# 胸外文献每日监控站 — 实施计划 v3

> v3 变更(用户最终决策):LLM 锁定 MiniMax M3 (`https://api.MiniMax.chat/v1` + `MiniMax-M3`);筛选组合 = AND;回填并发 = 3;详情页只显示 PubMed 链接;excluded_records 不暴露用户;仅时间倒序排序;**新增本地 Docker 预览工作流,满意后再上云服务器**。

---

## Context

目标:做一个类似 `https://aihot.virxact.com/all` 形态的胸外科**每日新文献监控站**,部署在 Ubuntu + Docker 云服务器。

**已确认关键决策**(用户 2026-07-31 全部确认):
- ✅ **每日监控**: 每日 8:00 北京时间抓前一天(UTC 0:00)
- ✅ **完全推倒从零搭建**,不借兄弟项目代码
- ✅ **暗色模式**: 默认跟随系统(`prefers-color-scheme`),三态切换,localStorage
- ✅ **首次回填 2026-07-20 ~ 2026-07-30 共 11 天**,并发度 3
- ✅ **PubMed API Key**: 用户提供(10 RPS)
- ✅ **LLM 锁定 MiniMax M3**: `https://api.MiniMax.chat/v1/chat/completions` + `MiniMax-M3`(OpenAI 兼容)
- ✅ **5 种研究类型**: 临床研究 / AI·ML 研究 / 基础研究 / 综述与 Meta / 指南与共识
- ✅ **5 种病种**: 肺癌 / 食管癌 / 纵隔肿瘤 / 气管疾病 / 气胸·胸外伤·肋骨骨折·胸壁畸形
- ✅ **单归属约束**: 同一篇文献只能属于 1 个 type + 1 个 disease
- ✅ **LLM 辅助**: 单选 type + 单选 disease + 中英翻译标题/摘要
- ✅ **卡片精简**: 来源 / 中英标题 / 时间戳 / tag(类型/病种/JCR 徽章),不显示摘要/收藏/engagement
- ✅ **详情页**: 标题(中英)/ 作者 / 作者单位 / 摘要(中英) / 类型/病种/分区/影响因子 / PubMed 原文链接(不显示 DOI)
- ✅ **侧边栏 3 组**: 内容(全部 / 周报预留)/ 主题(5 病种)/ 更多(关于/更新日志/反馈);底部暗色切换;删除"接入"分组
- ✅ **右侧仅搜索框**,删除来源下拉
- ✅ **筛选组合 = AND**,无需 OR
- ✅ **excluded_records 不暴露 UI**,仅 `/api/changelog` JSON 可见
- ✅ **排序仅时间倒序**(同一天内 fetched_at 倒序)
- ✅ **暂不 HTTPS** (`http://localhost:8080`)
- ✅ **本地 Docker 预览优先**: 做好后用户在自己 Mac 上跑 docker,Claude 与用户一起预览,满意后才部署云服务器

---

## 一、本地预览工作流(NEW v3)

### 1.1 两阶段交付模型

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase A:本地预览(Local-First,默认状态)                        │
│  ─────────────────────────────────────────                      │
│  1. 在用户 Mac 上 docker compose up                             │
│  2. 浏览器访问 http://localhost:8080                            │
│  3. Claude 与用户一起排查问题、修改 UI                          │
│  4. 反复迭代直至用户说"满意"                                   │
└─────────────────────────────────────────────────────────────────┘
                          ↓
              用户确认满意 ✓
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│  Phase B:云服务器部署(Production)                             │
│  ─────────────────────────────────────────                      │
│  1. 同一份 docker-compose.yml + .env(只换 host)                │
│  2. ./deploy.sh user@<server-ip> 推送镜像 + 启动                │
│  3. curl http://<server-ip>:8080/api/health 验证               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 本地预览的命令

```bash
# 在 Mac 上首次启动
cd ~/Documents/Claude\ Projects/Thoracic-Weekly-Server/

# 1. 准备环境
cp .env.example .env
nano .env   # 填入 PUBMED_API_KEY, LLM_API_KEY(MiniMax), REGEN_TOKEN

# 2. 构建并启动(包含回填)
docker compose up -d --build
docker compose run --rm cron python -m thoracic.pipeline.backfill \
  --from 2026-07-20 --to 2026-07-30 --concurrency 3

# 3. 构建 Astro 静态文件
cd web && npm ci && npm run build && cd ..

# 4. 重启 web 让其加载新构建
docker compose restart web

# 5. 浏览器访问
open http://localhost:8080
```

### 1.3 开发热重载(可选)

```bash
# 后端热重载:用 uvicorn --reload 替代 docker 容器
cd api && uv run uvicorn thoracic.main:app --reload --port 8080

# 前端热重载
cd web && npm run dev   # Astro dev server 在 :4321

# 浏览器访问 http://localhost:4321(注意是 Astro dev,不是 docker)
```

### 1.4 "满意"的判据

用户口头确认 + 验证清单(§十五)全部通过,方可进入 Phase B。

---

## 二、架构总览

```
                        本地 macOS Docker Desktop / Ubuntu + Docker
┌──────────────────────────────────────────────────────────────────┐
│                          docker-compose                            │
│                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐     │
│  │  thoracic-api    │  │  thoracic-cron  │  │ thoracic-static│     │
│  │  FastAPI :8080   │  │ supercronic 8:00│  │ nginx :80      │     │
│  │  (Python 3.12)   │  │ (Beijing)       │  │  Astro 静态构建 │     │
│  │                  │  │                 │  │ + 反代 /api/*   │     │
│  └────────┬─────────┘  └────────┬────────┘  └───────▲────────┘     │
│           │       SQLite /data/thoracic.db        │              │
│           └──────┬──────────────┬─────────────────┘              │
│                  │              │                                 │
│           ┌──────▼──────────────▼──────────────┐                  │
│           │  Docker volume: thoracic-data       │                  │
│           │  /data/thoracic.db                  │                  │
│           │  /data/snapshots/YYYY-MM-DD.json    │                  │
│           └─────────────────────────────────────┘                  │
│                                                                    │
│  outbound: cron 容器 → NCBI E-utilities + MiniMax API             │
└──────────────────────────────────────────────────────────────────┘

浏览器 ──http──► nginx :80
                 ├─ /              → Astro 静态构建
                 ├─ /api/*         → 反代 thoracic-api:8080
                 └─ /article/*     → Astro 静态构建
```

---

## 三、技术栈

| 层 | 选型 |
|---|---|
| 后端语言 | Python 3.12 |
| 后端框架 | FastAPI + Uvicorn |
| HTTP 客户端 | `httpx` (async) |
| 数据存储 | SQLite (WAL + FTS5) |
| 前端 | Astro 4 + React 19 island |
| 样式 | 原生 CSS + CSS Variables |
| LLM | MiniMax M3 (`https://api.MiniMax.chat/v1/chat/completions`, OpenAI 兼容) |
| 部署 | Docker Compose (3 容器) |
| 反代 | nginx 1.27 alpine |
| 调度 | supercronic (容器内) |
| 进程托管 | tini |

---

## 四、目录结构

```
Thoracic-Weekly-Server/
├── README.md                   # 含本地预览 + 云部署双流程
├── CLAUDE.md                   # 项目不变量
├── docker-compose.yml          # 同时支持本地与云(网络配置无差异)
├── deploy.sh                   # 仅 Phase B: scp 上云服务器 + 远端 docker compose up
├── Makefile                    # 本地常用命令(make up / make backfill / make logs ...)
├── .env.example                # 含 MiniMax M3 默认 base_url
├── .dockerignore
├── .gitignore
├── pyproject.toml              # uv 管理
├── uv.lock
│
├── api/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── src/thoracic/
│       ├── main.py
│       ├── config.py           # 含 LLM_BASE_URL=https://api.MiniMax.chat/v1
│       ├── db/
│       │   ├── schema.sql
│       │   ├── connection.py
│       │   ├── repo.py
│       │   └── seed.py
│       ├── pubmed/
│       │   ├── dates.py
│       │   ├── diseases.py     # 5 病种
│       │   ├── query.py
│       │   ├── client.py
│       │   ├── parser.py
│       │   ├── journal_terms.py
│       │   └── pubmed.py
│       ├── llm/
│       │   ├── client.py       # OpenAI 兼容(MiniMax M3)
│       │   ├── prompts/
│       │   │   ├── classify.py # 单选 type + 单选 disease + exclude
│       │   │   └── translate.py
│       │   ├── schemas.py
│       │   ├── cache.py        # hash(pmid) 缓存到 SQLite llm_cache 表
│       │   └── errors.py
│       ├── pipeline/
│       │   ├── daily.py
│       │   └── backfill.py
│       ├── api/
│       │   ├── routes.py
│       │   └── schemas.py
│       └── snapshots/
│           └── writer.py
│
├── cron/
│   ├── Dockerfile
│   ├── crontab
│   └── (与 api/ 共享 src/thoracic/)
│
├── web/
│   ├── package.json
│   ├── astro.config.mjs
│   ├── tsconfig.json
│   ├── public/{favicon.svg, logo.svg}
│   ├── src/
│   │   ├── env.d.ts
│   │   ├── layouts/BaseLayout.astro
│   │   ├── components/
│   │   │   ├── TopNav.astro
│   │   │   ├── Sidebar.astro
│   │   │   ├── FilterTabs.astro
│   │   │   ├── DateGroup.astro
│   │   │   ├── ArticleCard.astro
│   │   │   ├── JournalBadge.astro
│   │   │   └── SearchBox.astro
│   │   ├── islands/
│   │   │   ├── ThemeToggle.tsx  # 默认 system,三态切换
│   │   │   ├── Filter.tsx
│   │   │   └── Search.tsx
│   │   ├── styles/{tokens,base,layout,components}.css
│   │   ├── lib/{api.ts, types.ts}
│   │   └── pages/
│   │       ├── index.astro
│   │       ├── topics/
│   │       │   ├── index.astro
│   │       │   └── [slug].astro
│   │       ├── article/[pmid].astro
│   │       ├── about.astro
│   │       ├── changelog.astro
│   │       └── feedback.astro
│   └── tests/
│
├── references/
│   ├── journal_metrics.json
│   └── workflow.md             # 同步更新版
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── LOCAL_DEV.md            # 本地预览专章
│   ├── DEPLOY.md
│   └── BACKFILL.md
│
└── data/                       # .gitignore
    ├── thoracic.db
    └── snapshots/YYYY-MM-DD.json
```

---

## 五、检索规则 v3(同步更新到 `胸外科周报PubMed检索规则.md`)

### 5.1 5 种病种

| slug | 中文名 | 检索式核心字段 |
|---|---|---|
| `lung_cancer` | 肺癌 | `"Lung Neoplasms"[Mesh]` ∪ `lung cancer / NSCLC / SCLC / lung adenocarcinoma / lung squamous cell carcinoma` 等 `[tiab]` |
| `esophageal` | 食管癌 | `"Esophageal Neoplasms"[Mesh]` ∪ `esophageal cancer / ESCC / esophageal adenocarcinoma / esophageal squamous cell carcinoma` 等 `[tiab]` |
| `mediastinal` | 纵隔肿瘤 | `"Mediastinal Neoplasms"[Mesh]` ∪ `mediastinal tumor / thymoma / thymic carcinoma / thymic epithelial tumor / mediastinal germ cell tumor` 等 `[tiab]` |
| `tracheal` | 气管疾病 | `"Tracheal Neoplasms"[Mesh]` ∪ `"Tracheal Stenosis"[Mesh]` ∪ `tracheal cancer / tracheal tumor / tracheal stenosis / tracheal resection / airway surgery / tracheoplasty` 等 `[tiab]` |
| `chest_wall_injury` | 气胸·胸外伤·肋骨骨折·胸壁畸形 | `"Pneumothorax"[Mesh]` ∪ `"Thoracic Injuries"[Mesh]` ∪ `"Rib Fractures"[Mesh]` ∪ `"Pulmonary Contusion"[Mesh]` ∪ `"Funnel Chest"[Mesh]` ∪ `spontaneous pneumothorax / flail chest / SSRF / Nuss procedure / pectus excavatum / chest wall reconstruction` 等 `[tiab]` |

### 5.2 5 种研究类型

| slug | 中文名 | 候选 PubType 与关键词 |
|---|---|---|
| `clinical` | 临床研究 | `Clinical Trial` / `Randomized Controlled Trial` / `Multicenter Study` / `Observational Study` / `Cohort Study` / `Case-Control Study` / `Comparative Study` / `Validation Study` |
| `ai_ml` | 人工智能/机器学习研究 | `Machine Learning` / `Neural Networks, Computer` / `Artificial Intelligence`;标题含 `machine learning / deep learning / neural network / artificial intelligence / AI / ML / LLM / ChatGPT / CNN / RNN` |
| `basic_research` | 基础研究 | `Animals` / `Mice` / `Rats` / `Cell Line` / `In Vitro` / `Molecular` / `Genetic` / `Biochemical` 等 |
| `review` | 综述与 Meta | `Systematic Review` / `Meta-Analysis` / `Review` / `Narrative Review` |
| `guideline` | 指南与共识 | `Practice Guideline` / `Guideline` / `Consensus Development Conference` / `Clinical Conference` |

**单归属约束**: 每篇文献只输出 1 个 `type` + 1 个 `disease`。LLM 决定最准确的一个;若不确定则 `needs_review=true` 标记,UI 显示但保留待人工审核钩子(v2 后续)。

### 5.3 纵隔补检

严格纵隔检索为 0 结果时,放宽到 `"Mediastinum"[Mesh]` / `thymic[tiab]` / `anterior mediastinal[tiab]`,**人工筛选**,不自动并入。

### 5.4 时间窗

- PubMed 字段:`[epdat]` (Electronic Date of Publication)
- 单日区间:`YYYY/MM/DD:YYYY/MM/DD[epdat]`(左闭右闭)
- v3 改为"每日"模式,不再是周报

---

## 六、数据库 Schema v3

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS articles (
    pmid              TEXT PRIMARY KEY,
    title             TEXT NOT NULL,            -- 英文
    title_zh          TEXT NOT NULL,            -- LLM 翻译中文
    abstract          TEXT,                     -- 英文原文(可能为空)
    abstract_zh       TEXT,                     -- LLM 翻译中文
    authors           TEXT NOT NULL,            -- JSON [...]
    affiliations      TEXT,                     -- JSON [...] (与 authors 一一对应,允许 null)
    journal           TEXT NOT NULL,            -- PubMed 期刊词
    journal_full      TEXT,                     -- journal_metrics.json 匹配的全称
    journal_abbr      TEXT,
    publication_types TEXT NOT NULL,            -- JSON [...]
    pubdate           TEXT,                     -- "2026 Jul 21"
    epdat             TEXT NOT NULL,            -- "2026-07-29"
    fetched_at        TEXT NOT NULL,            -- 入库时间 ISO

    -- 单归属 1:1
    disease           TEXT NOT NULL,            -- lung_cancer / esophageal / mediastinal / tracheal / chest_wall_injury
    type              TEXT NOT NULL,            -- clinical / ai_ml / basic_research / review / guideline

    -- LLM 元数据
    llm_classified_at TEXT,
    llm_model         TEXT NOT NULL DEFAULT 'MiniMax-M3',
    llm_excluded      INTEGER NOT NULL DEFAULT 0,
    llm_exclude_reason TEXT,
    llm_needs_review  INTEGER NOT NULL DEFAULT 0,

    -- 期刊指标(从 journal_metrics.json 缓存)
    impact_factor     REAL,
    jcr_quartile      TEXT,
    new_talent_quartile TEXT,
    matched_jcr       TEXT
);

CREATE INDEX idx_articles_epdat ON articles(epdat);
CREATE INDEX idx_articles_disease ON articles(disease);
CREATE INDEX idx_articles_type ON articles(type);
CREATE INDEX idx_articles_journal ON articles(journal);
CREATE INDEX idx_articles_excluded ON articles(llm_excluded);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    date            TEXT PRIMARY KEY,
    generated_at    TEXT NOT NULL,
    article_count   INTEGER NOT NULL,
    total_fetched   INTEGER NOT NULL,
    excluded_count  INTEGER NOT NULL,
    by_disease_json TEXT,
    by_type_json    TEXT,
    llm_calls       INTEGER,
    llm_cost_usd    REAL,
    note            TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title, title_zh, abstract, abstract_zh, journal_full,
    content='articles', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, title_zh, abstract, abstract_zh, journal_full)
    VALUES (new.rowid, new.title, new.title_zh, new.abstract, new.abstract_zh, new.journal_full);
END;
CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, title_zh, abstract, abstract_zh, journal_full)
    VALUES ('delete', old.rowid, old.title, old.title_zh, old.abstract, old.abstract_zh, old.journal_full);
END;
CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, title_zh, abstract, abstract_zh, journal_full)
    VALUES ('delete', old.rowid, old.title, old.title_zh, old.abstract, old.abstract_zh, old.journal_full);
    INSERT INTO articles_fts(rowid, title, title_zh, abstract, abstract_zh, journal_full)
    VALUES (new.rowid, new.title, new.title_zh, new.abstract, new.abstract_zh, new.journal_full);
END;

CREATE TABLE IF NOT EXISTS run_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    kind            TEXT NOT NULL,
    target_date     TEXT,
    fetched_count   INTEGER,
    classified_count INTEGER,
    llm_calls       INTEGER,
    status          TEXT NOT NULL,
    error_msg       TEXT
);

CREATE TABLE IF NOT EXISTS excluded_records (
    pmid          TEXT PRIMARY KEY,
    hit_source    TEXT,
    title         TEXT,
    journal       TEXT,
    pubdate       TEXT,
    reason        TEXT NOT NULL
);

-- LLM 缓存(hash(pmid) → {type, disease, exclude, reason, title_zh, abstract_zh})
CREATE TABLE IF NOT EXISTS llm_cache (
    pmid_hash      TEXT PRIMARY KEY,
    payload_json   TEXT NOT NULL,
    model          TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    expires_at     TEXT
);
CREATE INDEX idx_llm_cache_expires ON llm_cache(expires_at);
```

---

## 七、API 端点

```
GET  /api/health
GET  /api/diseases                  ← 5 病种常量(可选,前端构建期硬编码也可)
GET  /api/types                     ← 5 类型常量(可选)
GET  /api/dates?limit=N
GET  /api/daily?date=YYYY-MM-DD&type=xxx&disease=xxx&limit=N&offset=M
GET  /api/all?type=xxx&disease=xxx&from=YYYY-MM-DD&to=YYYY-MM-DD&limit=N&offset=M
GET  /api/article/{pmid}            ← 详情页 JSON
GET  /api/changelog?limit=N         ← 含 excluded_records 数量(不暴露明细)
GET  /api/snapshots?limit=N
POST /api/backfill                  ← 鉴权 Bearer REGEN_TOKEN
```

**已删除**:`/api/topics` 与 `/api/topic/{slug}`(侧边栏主题分组已移除,筛选迁到顶部双层 chip)。

`/d/{slug}` 与 `/t/{slug}` 是 Astro 前端路由(路径映射),不直接对应后端 API;页面 SSR 时从 URL 读 `slug`,再调 `/api/all?disease=xxx` 或 `/api/all?type=xxx` 拿数据。

**筛选语义**: 所有条件 **AND**。无 OR 语义。

**`/api/changelog` 返回结构**:
```json
{
  "runs": [
    {"date":"2026-07-30","fetched":42,"published":38,"excluded":4,"llm_calls":5}
  ]
}
```
**不返回** excluded_records 明细(用户决策)。

---

## 八、LLM 集成(MiniMax M3)

### 8.1 `.env.example`

```env
# PubMed
PUBMED_API_KEY=

# MiniMax M3(用户提供 API Key)
LLM_BASE_URL=https://api.MiniMax.chat/v1
LLM_API_KEY=
LLM_MODEL=MiniMax-M3

# 调度
LLM_TIMEOUT_SECONDS=60
LLM_MAX_CONCURRENT=3
LLM_BATCH_SIZE=10

# 反向触发鉴权
REGEN_TOKEN=change-me-to-a-long-random-string

# 时区与存储
TZ=Asia/Shanghai
DB_PATH=/data/thoracic.db
SNAPSHOT_DIR=/data/snapshots

# 日志
LOG_LEVEL=INFO
```

### 8.2 客户端(`llm/client.py`)

```python
class MiniMaxClient:
    def __init__(self, base_url, api_key, model, timeout=60, max_concurrent=3):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def chat(self, messages: list[dict], response_format={"type":"json_object"}, max_retries=3) -> dict:
        async with self.semaphore:
            for attempt in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        r = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json={
                                "model": self.model,
                                "messages": messages,
                                "response_format": response_format,
                                "temperature": 0.2,
                            },
                        )
                        r.raise_for_status()
                        return r.json()
                except (httpx.HTTPError, json.JSONDecodeError) as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
```

### 8.3 合并 prompt(`classify_and_translate` 一次调用)

```
SYSTEM:
你是胸外科文献分类与翻译助手。对每篇 PubMed 文献,输出严格 JSON(无 markdown):
{
  "items": [
    {
      "pmid": "...",
      "type": "clinical" | "ai_ml" | "basic_research" | "review" | "guideline",
      "disease": "lung_cancer" | "esophageal" | "mediastinal" | "tracheal" | "chest_wall_injury",
      "exclude": false,
      "exclude_reason": null,
      "title_zh": "中文标题,翻译自然流畅,保留专有名词原英文",
      "abstract_zh": "中文摘要,翻译自然流畅,保留医学术语与原英文"
    }
  ]
}

type 与 disease 各只输出 1 个最准确的。若文献不符合 5 大病种之一,或为 letter/news/editorial/abstract-only,设 exclude=true。

USER:
[
  {"pmid":"...","title":"...","abstract":"...","publication_types":["..."],"mesh_terms":["..."]},
  ...
]
```

### 8.4 缓存 + 失败兜底

```python
async def classify_and_translate_batch(records):
    # 1. 命中缓存直接返回
    uncached = [r for r in records if not llm_cache.get(r.pmid)]
    if not uncached:
        return [apply_cached(r) for r in records]

    # 2. 批 10 篇一次调用,失败重试 3 次
    try:
        chunks = chunked(uncached, settings.LLM_BATCH_SIZE)
        results = await asyncio.gather(*[llm_client.chat(...) for chunk in chunks])
        parsed = parse_response(results)
    except Exception as e:
        log.error(f"LLM call failed: {e}; falling back to heuristic")
        # 兜底:用 PubType 启发式,翻译字段留空
        return [heuristic_fallback(r) for r in records]

    # 3. 写缓存
    for r, llm_out in zip(uncached, parsed):
        llm_cache.set(r.pmid, llm_out, ttl=86400 * 365)
        apply_llm_to_record(r, llm_out)
    return records
```

### 8.5 兜底降级

LLM 完全失败时:
- `type` 取命中最多 PubType 映射的 1 个
- `disease` 取 esearch 命中来源的 1 个
- `title_zh` / `abstract_zh` 留空(前端显示英文)
- `llm_excluded=0`,`llm_needs_review=1`(后续 v2 审核入口)

---

## 九、抓取 → LLM → 入库完整流程

```python
async def run_daily(target_date: date):
    # 1. 5 病种 esearch
    epdat = f"{target_date}:{target_date}[epdat]"
    pmids_by_disease = await gather_esearch(build_queries(epdat))

    # 2. efetch 200/批(POST)
    raw = await gather_efetch(union(pmids_by_disease.values()), 200)

    # 3. 解析 + 记录 disease_hint(LLM 兜底用)
    records = parse_xml(raw)
    for r in records:
        r.disease_hint = first_disease(r.pmid, pmids_by_disease)

    # 4. LLM 分类 + 翻译(批 10/次,失败兜底)
    enriched = await classify_and_translate_batch(records)

    # 5. join journal_metrics → stamp IF/Q1/新锐
    for r in enriched: stamp_journal_metrics(r, metrics_index)

    # 6. 拆分:publish / exclude
    to_publish = [r for r in enriched if not r.llm_excluded]
    to_exclude = [r for r in enriched if r.llm_excluded]
    upsert_articles(conn, to_publish)
    upsert_excluded_records(conn, to_exclude)

    # 7. daily_snapshots 元数据
    upsert_snapshot(conn, target_date, to_publish)

    # 8. JSON snapshot(Astro 构建期读取)
    write_snapshot(target_date, to_publish)

    # 9. run_log
    log_run(...)
```

---

## 十、Cron 配置

`cron/crontab`:
```
# 北京时间 8:00 抓取前一天(UTC 0:00)
0 0 * * * cd /app && python -m thoracic.pipeline.daily --target $(TZ=Asia/Shanghai date -d 'yesterday' +%Y-%m-%d) >> /var/log/cron.log 2>&1

# 每周一 10:00 北京时间清理 180 天前 snapshot JSON
0 2 * * 1 cd /app && python -m thoracic.pipeline.cleanup --older-than 180 >> /var/log/cron.log 2>&1
```

`TZ=Asia/Shanghai date -d 'yesterday'` 强制按 Beijing 时区计算前一天,避免容器时区漂移。

---

## 十一、前端页面

### 11.1 路由

| 路径 | 说明 |
|---|---|
| `/` | 全部文献(默认页,按 epdat 倒序;顶部双层筛选) |
| `/article/{pmid}` | 详情页 |
| `/about` | 关于 |
| `/changelog` | 更新日志 |
| `/feedback` | 反馈 |
| `/d/{slug}` | 单病种深链接(`/d/lung-cancer`,与 `/?disease=lung_cancer` 等价;便于分享) |
| `/t/{slug}` | 单研究类型深链接(`/t/clinical`,与 `/?type=clinical` 等价) |

**已删除**:`/topics` 与 `/topics/{slug}` 路由 —— 主题/类型筛选已统一到顶部双层筛选栏;深链接通过 `/d/{slug}` 与 `/t/{slug}` 提供。

### 11.2 顶部双层筛选栏(病种 + 研究类型)

主区顶部紧邻搜索框下方,2 行 chip 筛选:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 病种  [全部] [肺癌] [食管癌] [纵隔肿瘤] [气管疾病] [气胸·胸外伤]  │  ← 行 1(5 病种 + 全部)
│ 类型  [全部] [临床研究] [AI/ML] [基础研究] [综述Meta] [指南共识]   │  ← 行 2(5 类型 + 全部)
└─────────────────────────────────────────────────────────────────────┘
```

**URL 同步**(全部条件 AND):
- `/?disease=lung_cancer` — 仅肺癌
- `/?type=clinical` — 仅临床研究
- `/?disease=lung_cancer&type=ai_ml` — 肺癌 **且** AI/ML(很窄)
- `/?disease=lung_cancer&type=clinical` — 肺癌 **且** 临床研究
- `?` 无参数 — 全部文献(两个"全部"高亮)

**激活态视觉**: teal `#0d9488`(亮) / `#2dd4bf`(暗) 文字 + 底部 2px 强调线 + 背景 `#ecfeff`(亮) / `#164e63`(暗)。
**未激活态**: 灰边框 `#e5e7eb`(亮) / `#1f2937`(暗),透明背景。
**Hover**: 背景轻微加深,过渡 150ms。
**点击行为**: 点击某 chip = URL 替换该参数 + 重新拉数据;点击当前激活的 chip = 取消该参数(回到"全部")。

**组件**:`Filter.tsx`(React island,挂载在 layout 中,监听 URL + 反向同步)。
**数据来源**: `/api/diseases`(返回 5 个病种中文名)+ `/api/types`(返回 5 个类型中文名)。这两个端点是常量,前端构建期硬编码亦可(避免每次请求)。

**响应式**: 移动端(< 768px)时,两行 chip 自动水平滚动(不换行),避免换行破坏视觉节奏。

### 11.3 主区卡片(精简)

```
┌──────────────────────────────────────────────────────────────┐
│ Lancet (Lancet)                                              │  ← 来源
│                                                              │
│ 微软件 2026 财年第四财季业绩会实录:算力供给依然不足...      │  ← 标题(中文)
│ Microsoft FY2026 Q4 earnings: compute supply still insufficient│  ← 标题(英文,灰色)
│                                                              │
│ 2026-07-29                                                    │  ← 时间戳
│                                                              │
│ [临床研究] [肺癌] [Q1] [IF 84.5] [新锐1区]                    │  ← tag
└──────────────────────────────────────────────────────────────┘
```

不含摘要、收藏、engagement。

### 11.4 详情页 `/article/{pmid}`

```
┌──────────────────────────────────────────────────────────────┐
│  ← 返回 全部文献                                              │
│                                                              │
│ 中文标题(主,大字)                                            │
│ English Title (副,小字,灰色)                                  │
│                                                              │
│ 期刊:Lancet (Lancet)                                         │
│ PMID: 39012345                                                │
│ 原文链接:https://pubmed.ncbi.nlm.nih.gov/39012345/           │
│ 发布日期:2026-07-29                                          │
│                                                              │
│ 作者:                                                       │
│ • Author A — Author A, B Affiliation                        │
│ • Author B — Author A, B Affiliation                        │
│ • Author C — C Affiliation                                  │
│                                                              │
│ 作者单位:                                                    │
│ • Author A, B Affiliation                                    │
│ • C Affiliation                                              │
│                                                              │
│ ── 摘要 ──                                                   │
│ 中文摘要(LLM 翻译):                                        │
│ 微软件 2026 财年第四财季 Azure 增速达 43%...                 │
│                                                              │
│ English Abstract:                                            │
│ Microsoft FY2026 Q4 Azure growth reached 43%...             │
│                                                              │
│ ── 分类与指标 ──                                             │
│ 研究类型: 临床研究                                            │
│ 病种: 肺癌                                                    │
│ JCR 分区: Q1                                                  │
│ 影响因子: 84.5                                                │
│ 新锐分区: 1区                                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

不显示 DOI。

### 11.5 右侧控件

仅搜索框(标题/摘要 FTS5,200ms debounce)。**无来源下拉**。

### 11.6 暗色模式(默认跟随系统)

```css
/* tokens.css */
:root {
  --bg: #ffffff; --fg: #0f172a; --accent: #0d9488;
  --border: #e5e7eb; --card-bg: #f9fafb; --muted: #6b7280;
  --link: #1d4ed8; --tag-bg: #ecfeff; color-scheme: light;
}
:root[data-theme='dark'] {
  --bg: #0a0e1a; --fg: #e5e7eb; --accent: #2dd4bf;
  --border: #1f2937; --card-bg: #111827; --muted: #9ca3af;
  --link: #60a5fa; --tag-bg: #164e63; color-scheme: dark;
}
```

`BaseLayout.astro` 头部内联(默认跟随系统):
```html
<script is:inline>
  const stored = localStorage.getItem('theme');
  const sys = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', stored ?? sys);
</script>
```

三态切换按钮 island:
```tsx
const order = ['system', 'light', 'dark'] as const;
const next = () => {
  const cur = (localStorage.getItem('theme-pref') as any) ?? 'system';
  const idx = order.indexOf(cur);
  const target = order[(idx + 1) % 3];
  localStorage.setItem('theme-pref', target);
  if (target === 'system') {
    document.documentElement.setAttribute('data-theme',
      matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  } else {
    document.documentElement.setAttribute('data-theme', target);
  }
};
// 默认值 'system';首次访问未点过按钮时,跟随系统
```

### 11.7 侧边栏(v4 精简版)

```
THORACIC
─────────────
内容
├ 全部文献             ← 激活态高亮(默认)
└ 周报 (即将上线)

更多
├ 关于
├ 更新日志
└ 反馈

─────────────
[🖥️ 系统] [☀️ 亮] [🌙 暗]   ← 暗色三态切换
```

**已删除**:"接入"分组、"精选"、"收藏"、**"主题"分组**(5 病种已迁入顶部双层筛选栏)。

**保留**: 内容(全部 + 周报预留)、更多、关于 / 更新日志 / 反馈、暗色三态切换。

侧边栏精简后仅 2 分组(内容 + 更多),视觉上更轻盈;5 病种的入口已完全在主区顶部 chip,深链可通过 `/d/{slug}` 分享。

---

## 十二、Docker Compose(本地与云共用)

```yaml
version: '3.9'

services:
  api:
    build:
      context: .
      dockerfile: api/Dockerfile
    image: thoracic-server:local
    container_name: thoracic-api
    restart: unless-stopped
    env_file: .env
    volumes:
      - thoracic-data:/data
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    expose: ["8080"]

  cron:
    build:
      context: .
      dockerfile: cron/Dockerfile
    image: thoracic-server:local
    container_name: thoracic-cron
    restart: unless-stopped
    env_file: .env
    volumes:
      - thoracic-data:/data
    depends_on:
      api: { condition: service_healthy }

  web:
    image: nginx:1.27-alpine
    container_name: thoracic-web
    restart: unless-stopped
    depends_on:
      api: { condition: service_healthy }
    ports:
      - "8080:80"
    volumes:
      - ./web/dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro

volumes:
  thoracic-data:
```

**本地与云无差别**,唯一区别是 deploy.sh(云服务器推送)。

---

## 十三、Makefile(本地预览便捷命令)

```makefile
.PHONY: up down backfill rebuild-web logs health

up:
	docker compose up -d --build

down:
	docker compose down

backfill:
	docker compose run --rm cron python -m thoracic.pipeline.backfill \
	  --from 2026-07-20 --to 2026-07-30 --concurrency 3

rebuild-web:
	cd web && npm ci && npm run build && cd ..
	docker compose restart web

logs:
	docker compose logs -f

health:
	curl -s http://localhost:8080/api/health | jq .

dev-api:
	cd api && uv run uvicorn thoracic.main:app --reload --port 8080

dev-web:
	cd web && npm run dev
```

---

## 十四、deploy.sh(Phase B 云服务器部署)

```bash
#!/usr/bin/env bash
set -euo pipefail
SERVER="${1:?Usage: ./deploy.sh user@server-ip}"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> 构建本地镜像"
docker build -t thoracic-server:local api/
docker build -t thoracic-server:local -f cron/Dockerfile .

echo "==> 打包源码与 nginx 配置"
tar czf /tmp/thoracic.tar.gz \
  --exclude='node_modules' --exclude='dist' --exclude='.git' \
  --exclude='.DS_Store' --exclude='data' \
  -C "$LOCAL_DIR" .

echo "==> 推送到 $SERVER"
scp /tmp/thoracic.tar.gz "$SERVER:~/"

echo "==> 远端构建并启动"
ssh "$SERVER" <<'REMOTE'
  cd ~
  tar xzf thoracic.tar.gz -C thoracic-server/
  cd thoracic-server
  docker compose build
  docker compose up -d
  docker compose run --rm cron python -m thoracic.pipeline.backfill \
    --from 2026-07-20 --to 2026-07-30 --concurrency 3
  cd web && npm ci && npm run build && cd ..
  docker compose restart web
REMOTE

echo "==> 部署完成。访问 http://<server-ip>:8080"
```

---

## 十五、依赖清单

### Python (`api/pyproject.toml`)
```toml
[project]
name = "thoracic-server"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "aiosqlite>=0.20",
    "httpx>=0.27",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "python-dateutil>=2.9",
]
```

### Astro (`web/package.json`)
```json
{
  "name": "thoracic-web",
  "type": "module",
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "test": "vitest"
  },
  "dependencies": {
    "astro": "^4.16",
    "@astrojs/react": "^3.6",
    "react": "^19.0",
    "react-dom": "^19.0"
  },
  "devDependencies": {
    "@types/react": "^19.0",
    "@types/react-dom": "^19.0",
    "typescript": "^5.7",
    "vitest": "^2.1",
    "@testing-library/react": "^16.0"
  }
}
```

---

## 十六、首次部署步骤(本地预览 Phase A)

```bash
# 在 Mac 上
cd ~/Documents/Claude\ Projects/Thoracic-Weekly-Server/

# 1. 准备环境
cp .env.example .env
nano .env
# 必须填: PUBMED_API_KEY, LLM_API_KEY, REGEN_TOKEN
# LLM_BASE_URL 默认为 https://api.MiniMax.chat/v1 (可保留)
# LLM_MODEL 默认为 MiniMax-M3 (可保留)

# 2. 构建并启动
make up

# 3. 健康检查
make health

# 4. 首次回填 11 天(并发 3)
make backfill

# 5. 构建 Astro
make rebuild-web

# 6. 浏览器访问
open http://localhost:8080
```

**预计回填时长**:
- 抓取(API Key 10 RPS): 5 病种 × 5 chunks × 0.5s ≈ 13 分钟
- LLM 调用(批 10/次): ~200 篇 / 10 = 20 次调用 × 2 秒 ≈ 40 秒
- 总: ~15 分钟

---

## 十七、验证清单(End-to-End)

| # | 测试 | 预期结果 |
|---|---|---|
| 1 | `make health` | `{"status":"ok","db":true,"snapshots":>=1}` |
| 2 | `curl /api/dates` | 返回 11 个日期 |
| 3 | `curl /api/daily?date=2026-07-30` | 含 `title/title_zh/abstract_zh/authors/affiliations/disease/type/jcr_quartile/impact_factor` |
| 4 | `curl /api/article/{任一pmid}` | 单篇完整详情(中英标题/作者/单位/摘要/指标/PubMed 链接,**无 DOI**) |
| 5 | `curl /api/all?type=clinical` | 仅临床研究 |
| 6 | `curl /api/all?disease=tracheal` | 仅气管疾病 |
| 7 | `curl /api/all?type=ai_ml&disease=lung_cancer` | AI/ML **且** 肺癌(很窄) |
| 8 | `curl /api/diseases` | 5 病种常量 |
| 9 | `curl /api/types` | 5 类型常量 |
| 10 | `curl /api/changelog?limit=5` | 含 excluded 数量,**不含** PMID 明细 |
| 11 | 浏览器 `/` | 顶部**双层筛选**(病种 6 chip + 类型 6 chip),URL 同步,按 epdat 倒序 |
| 12 | 浏览器 `/?disease=tracheal` | 仅气管疾病(顶部 chip 反映激活态) |
| 13 | 浏览器 `/?type=ai_ml` | 仅 AI/ML 研究 |
| 14 | 浏览器 `/?disease=lung_cancer&type=clinical` | 肺癌 **且** 临床研究(AND) |
| 15 | 浏览器 `/d/tracheal` | 等价于 `/?disease=tracheal`,便于分享 |
| 16 | 浏览器 `/t/clinical` | 等价于 `/?type=clinical`,便于分享 |
| 17 | 浏览器 `/article/{pmid}` | 中英标题/作者/单位/摘要/指标/PubMed 链接(无 DOI) |
| 18 | 浏览器首次访问 | 暗色跟随系统(prefers-color-scheme) |
| 19 | 浏览器点击暗色按钮 | 三态切换 system/light/dark,刷新保持 |
| 20 | 第二天 8:00 后 | 新增当日条目 |
| 21 | LLM 临时不可用 | 数据仍能入库(PubType 兜底,title_zh 留空) |

---

## 十八、已确认决策清单(用户答复)

1. ✅ LLM = **MiniMax M3** (`https://api.MiniMax.chat/v1` + `MiniMax-M3`)
2. ✅ 筛选组合语义 = **AND**,无 OR
3. ✅ 首次回填 `--concurrency` = **3**
4. ✅ 详情页只显示 **PubMed 链接**,不显示 DOI
5. ✅ `excluded_records` **不暴露用户**,仅 `/api/changelog` JSON 汇总
6. ✅ 仅**时间倒序**排序(同一天 fetched_at 倒序)
7. ✅ **本地 Docker 预览优先**: 做好后用户在自己 Mac 上跑 docker,Claude 与用户一起预览,满意后再上云服务器

---

## 十九、风险与缓解 v3

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| MiniMax M3 API 限流 | 中 | 高 | semaphore=3 + 重试 3 次 + 失败降级 PubType 兜底 |
| MiniMax 翻译医学术语不准确 | 中 | 中 | prompt 含"保留专有名词";hash(pmid) 一年缓存 |
| MiniMax 单选 type/disease 错误 | 中 | 中 | `llm_needs_review=1` 标记,后续 v2 审核入口 |
| 5 病种检索式重叠(对照研究同时命中) | 高 | 中 | esearch 按 PMID 去重;LLM 强制单选 disease |
| SQLite 并发写冲突 | 低 | 高 | WAL + cron 独占写,api 只读 |
| Astro 构建期数据 stale | 中 | 低 | `make rebuild-web` 手动触发 |
| macOS 与 Linux 容器差异(LF 换行、文件权限) | 低 | 中 | `.gitattributes` 强制 LF;docker compose volumes 命名卷绕开权限 |
| `[epdat]` 漏检索引滞后论文 | 低 | 中 | v1 接受,后续可对比 `[edat]` |
| cron outbound 限制(MiniMax/PubMed) | 低 | 高 | docker 默认放行,文档指出需放行 `eutils.ncbi.nlm.nih.gov` 与 `api.MiniMax.chat` |
| 11 天回填期间 cron 误触发 | 低 | 中 | `docker compose stop cron` 暂停,回填后再 `start` |

---

## 二十、未来扩展(明确不在 v1)

- 周报模式
- 用户账号 + 跨设备收藏
- RSS 订阅
- 微信公众号 / 飞书推送
- FTS5 中文分词优化
- HTTPS / 域名 / Let's Encrypt
- Astro 自动重建钩子(cron → webhook → build)
- `llm_needs_review=1` 文献的人工审核界面
- 期刊订阅推送
- 影响因子/分区排序选项

---

## 二十一、实施顺序(两阶段交付)

### Phase A:本地预览(Mac 上)

1. **脚手架** — `pyproject.toml` + `api/Dockerfile` + `cron/Dockerfile` + `docker-compose.yml` + `nginx.conf` + `.env.example` + `Makefile`
2. **数据库** — `db/schema.sql` + `db/connection.py` + `db/repo.py` + `db/seed.py`
3. **PubMed 检索** — `pubmed/{dates,diseases,query,client,parser,journal_terms,pubmed}.py`
4. **LLM 客户端(MiniMax)** — `llm/client.py` + `llm/prompts/{classify,translate}.py` + `llm/{schemas,cache,errors}.py`
5. **LLM 任务** — `classify_and_translate_batch()` + 缓存 + 失败兜底
6. **daily pipeline** — `pipeline/daily.py` + `pipeline/backfill.py`
7. **API 层** — `api/routes.py` + `api/schemas.py`
8. **首次回填** — `make backfill`,验证 SQLite + snapshot
9. **Astro 脚手架** — `web/` + `astro.config.mjs` + `tokens.css` + `BaseLayout.astro`
10. **静态页面** — `pages/{index,topics/[slug],article/[pmid],about,changelog,feedback}.astro`
11. **组件** — `components/{TopNav,Sidebar,FilterTabs,DateGroup,ArticleCard,JournalBadge,SearchBox}.astro`
12. **交互 island** — `islands/{ThemeToggle,Filter,Search}.tsx`(暗色默认 system)
13. **本地预览与迭代** — `make up` + `make rebuild-web`,浏览器看效果,与 Claude 排查问题
14. **用户确认满意** — 口头"OK,可以上云了"

### Phase B:云服务器部署(用户点头后)

15. **`deploy.sh user@server-ip`** — 推送镜像 + 远端回填 + 远端构建
16. **云服务器验证** — `curl http://<server-ip>:8080/api/health`
17. **第二日 cron 验证** — 检查 `docker compose logs -f cron` 与 `/api/changelog`

---

## 二十二、关键文件路径索引

- 检索规则源(待更新到 v3):`/Users/linastro/Documents/Claude Projects/Thoracic-Weekly-Server/胸外科周报PubMed检索规则.md`
- 期刊白名单:`/Users/linastro/Documents/Claude Projects/Thoracic-Weekly-Server/journal_metrics.json`(114 本)
- 参考实现(Python):`/Users/linastro/.claude/skills/thoracic-weekly-academy/scripts/search_pubmed_weekly.py`
- MiniMax M3 端点(兄弟项目已验证):`https://api.MiniMax.chat/v1/chat/completions` + `MiniMax-M3`
- 历史周报(LinDocuments, 供回填参考):`/Users/linastro/Documents/LinDocuments/文稿/医学/胸外pro/7职务/宣传/公众号/※科研周报/thoracic_weekly_2026-07-20_2026-07-26/`
- aihot 站点参考:`https://aihot.virxact.com/all`
- NCBI E-utilities:`https://www.ncbi.nlm.nih.gov/books/NBK25500/`