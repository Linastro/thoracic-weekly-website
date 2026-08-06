# 胸外文献每日监控 — PubMed 检索与分类规则

> 用途:汇总 PubMed 上检索胸外科每日新文献的核心规则——入库时间(`[edat]`)、病种分类、研究类型分类、检索式组装、筛选规范、LLM 辅助分类、可用工具与调用方式。供后续手工或脚本化检索直接复用。
>
> **本版本基于 v4 plan**: 单日监控(非周报),5 病种 × 5 研究类型,单归属,LLM(MiniMax M3)辅助。

---

## 一、文献入库时间:`[edat]` 确定

### 1.1 规则核心

- PubMed 检索的时间**严格**采用 **Entrez Date (PubMed 入库日)**,字段标识为 **`[edat]`**。
- 时间窗为**前一个完整入库日**(美东日历日 = 北京昨天中午到今天中午进库的那批),**不使用** `[dp]`、`[pdat]`、`[epdat]`、`last 7 days`、滚动时间窗(除非显式覆盖)。
- 检索式片段格式:`YYYY/MM/DD:YYYY/MM/DD[edat]`(左闭右闭,单日区间)。
- **入库日翻页点 = 美东午夜**(北京 12:00 夏令时 / 13:00 冬令时);某入库日封口后永不再变,单日检索即完整、无需回看两天。

### 1.2 日期换算示例

| 当前日期(Beijing) | 抓取目标日(美东"昨天") | 检索式片段 |
|---|---|---|
| 2026-07-29(周三) | 2026-07-28(周二) | `2026/07/28:2026/07/28[edat]` |
| 2026-08-01(周五) | 2026-07-31(周四) | `2026/07/31:2026/07/31[edat]` |
| 2026-07-31(周四) | 2026-07-30(周三) | `2026/07/30:2026/07/30[edat]` |

> 每日 cron 在 **北京时间 14:00** 触发(美东凌晨,入库日翻页后 1-2 小时),抓取美东"昨天"的 `[edat]` 单日区间。

### 1.3 计算逻辑(Python 通用实现)

```python
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

def previous_us_eastern_day(now: datetime | None = None) -> date:
    """返回美东时区的"昨天" = 前一个完整 PubMed 入库日。"""
    if now is None:
        now = datetime.now(ZoneInfo("America/New_York"))
    else:
        now = now.astimezone(ZoneInfo("America/New_York"))
    return (now - timedelta(days=1)).date()
```

调用示例:
```python
target = previous_us_eastern_day()
# 北京 14:00 运行 → target = date(美东昨天) = 前一个完整入库日
edat_clause = f"{target.isoformat()}:{target.isoformat()}[edat]"
# "2026/08/05:2026/08/05[edat]"
```

---

## 二、检索结构(五个病种 × 五类研究)

将胸外科相关文献按**病种分为 5 类**,每个病种内再按**研究类型分为 5 类**。

### 2.1 病种分类(5 类)

| slug | 序号 | 病种 | 检索式核心字段 |
|---|---|---|---|
| `lung_cancer` | 1 | 肺癌 | `"Lung Neoplasms"[Mesh]` ∪ `lung cancer / NSCLC / SCLC / lung adenocarcinoma / lung squamous cell carcinoma` 等 `[tiab]` |
| `esophageal` | 2 | 食管癌 | `"Esophageal Neoplasms"[Mesh]` ∪ `esophageal cancer / ESCC / esophageal adenocarcinoma / esophageal squamous cell carcinoma` 等 `[tiab]` |
| `mediastinal` | 3 | 纵隔肿瘤 | `"Mediastinal Neoplasms"[Mesh]` ∪ `mediastinal tumor / thymoma / thymic carcinoma / thymic epithelial tumor / mediastinal germ cell tumor` 等 `[tiab]` |
| `tracheal` | 4 | 气管疾病 | `"Tracheal Neoplasms"[Mesh]` ∪ `"Tracheal Stenosis"[Mesh]` ∪ `tracheal cancer / tracheal tumor / tracheal stenosis / tracheal resection / airway surgery / tracheoplasty` 等 `[tiab]` |
| `chest_wall_injury` | 5 | 气胸·胸外伤·肋骨骨折·胸壁畸形 | `"Pneumothorax"[Mesh]` ∪ `"Thoracic Injuries"[Mesh]` ∪ `"Rib Fractures"[Mesh]` ∪ `"Pulmonary Contusion"[Mesh]` ∪ `"Funnel Chest"[Mesh]` ∪ `spontaneous pneumothorax / flail chest / SSRF / Nuss procedure / pectus excavatum / chest wall reconstruction` 等 `[tiab]` |

> ⚠ **第五类为合并组**:气胸 / 胸部外伤 / 肋骨骨折 / 胸壁畸形 / 漏斗胸 在分类时合并为一组,而不是五个独立组。
>
> ⚠ **纵隔肿瘤补检**:若严格纵隔肿瘤检索 0 结果,可放宽到宽泛的纵隔/胸腺检索(包含 `"Mediastinum"[Mesh]` / `thymic[tiab]` / `anterior mediastinal[tiab]` 等),再**人工筛选**;不得将放宽结果自动并入。

### 2.2 研究类型分类(每病种下 5 类)

| slug | 序号 | 研究类型 | 适用文献 / 候选 PubType |
|---|---|---|---|
| `clinical` | 1 | 临床研究 | 原创性临床研究 + `Clinical Trial` / `Randomized Controlled Trial` / `Multicenter Study` / `Observational Study` / `Cohort Study` / `Case-Control Study` / `Comparative Study` / `Validation Study` |
| `ai_ml` | 2 | 人工智能/机器学习研究 | AI/ML 模型开发与验证 + `Machine Learning` / `Neural Networks, Computer` / `Artificial Intelligence`;标题含 `machine learning / deep learning / neural network / artificial intelligence / AI / ML / LLM / ChatGPT / CNN / RNN` |
| `basic_research` | 3 | 基础研究 | 湿实验、组学、机制研究、动物/细胞实验 + `Animals` / `Mice` / `Rats` / `Cell Line` / `In Vitro` / `Molecular` / `Genetic` / `Biochemical` |
| `review` | 4 | 综述与 Meta | 系统综述 / Meta 分析 + `Systematic Review` / `Meta-Analysis` / `Review` / `Narrative Review` |
| `guideline` | 5 | 指南与共识 | 临床指南 / 共识声明 + `Practice Guideline` / `Guideline` / `Consensus Development Conference` / `Clinical Conference` |

### 2.3 单归属约束(每篇 1 个 type + 1 个 disease)

- **每篇文献只输出 1 个 `type`**(LLM 在多 PubType 同时命中时选择最准确的 1 个)
- **每篇文献只输出 1 个 `disease`**(esearch 阶段按 PMID 去重;LLM 强制单选)
- 若文献在多个病种检索式中都命中(对照/合并研究),LLM 选择主病种,仅在该主病种选项卡显示
- 单归属约束保证前端筛选组合语义 = AND,无需 OR

---

## 三、检索范围(期刊 Scope)

- 期刊白名单维护于本地文件 **`journal_metrics.json`**,字段:
  - `journal`:期刊全称
  - `pubmed_journal_terms`:PubMed 期刊词列表(全称/缩写/常用别名)
  - `jcr_quartile`:JCR 分区(Q1–Q4)
  - `impact_factor`:影响因子
  - `new_talent_quartile`:新锐分区
  - `categories` / `category_quartiles`:学科分类与多分区
  - `matched_jcr_journal`:命中证据
- 若某条纳入文献的期刊在 `journal_metrics.json` 中无法匹配全称/缩写/PubMed 期刊词,显示 **`未缓存`**,不得用其他分区替代 `new_talent_quartile`。
- 为避免 E-utilities URL 过长或失败,建议将期刊词拆为多个 chunk(每 chunk 18 个左右)。
- 单次 `esearch` 的 `retmax` 建议 ≤ 500。
- **当前白名单共 114 本期刊,138 个 PubMed 期刊词**(2026-06-22 数据)。

---

## 四、检索式最终形态

对每个病种 `d`,期刊 chunk `j`,组装形式:

```text
(( <disease_query_for_d> ) AND ( "<j1>"[jour] OR "<j2>"[jour] OR ... OR "<jn>"[jour] ) AND <YYYY/MM/DD:YYYY/MM/DD[edat]>)
```

示例(肺癌第 1 个期刊 chunk,目标日 2026-07-28):

```text
(( "Lung Neoplasms"[Mesh] OR lung cancer[tiab] OR NSCLC[tiab] OR SCLC[tiab] OR lung adenocarcinoma[tiab] OR lung squamous cell carcinoma[tiab] )
 AND
 ( "Lancet"[jour] OR "Lancet Oncol"[jour] OR "J Clin Oncol"[jour] OR ... )
 AND
 2026/07/28:2026/07/28[edat])
```

---

## 五、筛选与分类规则

### 5.1 纳入(LLM 辅助判断)

- 原创性临床研究。
- 系统综述与 Meta 分析。
- 与目标病种高度相关的转化/基础研究。
- 与目标病种紧密绑定的机制或平台综述。
- 临床指南 / 共识声明。
- AI/ML 模型开发与验证、医学影像 AI、数字健康 AI。

### 5.2 排除(LLM 输出 `exclude=true`,进入 `excluded_records` 表)

- 新闻、简讯、研究摘要、作者感言、回复、无原始数据的 letter、社论、评论。
- 仅**附带**提及目标病种的记录。
- 主病种不属于五大病种,即便目标病种作为对照/协变量/次要讨论出现。
- 第四类与纵隔的**假阳性命中**:相关词仅作为影像征象、并发症描述或解剖学术语出现。
- 仅发表 abstract 但无全文的会议摘要。

### 5.3 LLM 分类与翻译(MiniMax M3)

每篇新抓取的文献都过一遍 LLM,返回 JSON:

```json
{
  "pmid": "39012345",
  "type": "clinical",
  "disease": "lung_cancer",
  "exclude": false,
  "exclude_reason": null,
  "title_zh": "中文标题(LLM 翻译,自然流畅,保留专有名词原英文)",
  "abstract_zh": "中文摘要(LLM 翻译,自然流畅,保留医学术语与原英文)"
}
```

**LLM 配置**:
- base_url:`https://api.MiniMax.chat/v1`
- model:`MiniMax-M3`
- 单次调用 1 个批次(默认 10 篇),temperature=0.2,`response_format={"type":"json_object"}`

**批 10 + 重试 3 + 失败降级**:
- LLM 临时不可用 → 重试 3 次指数退避(1s/2s/4s)
- 仍失败 → 用 PubType 启发式降级:
  - `type` 取命中最多 PubType 映射的 1 个
  - `disease` 取 esearch 命中来源的 1 个
  - `title_zh` / `abstract_zh` 留空(前端显示英文)
  - `llm_needs_review=1`(后续 v2 审核入口)

### 5.4 排除审计表(`excluded_records`)

| 字段 | 含义 |
|---|---|
| `pmid` PK | PubMed ID |
| `hit_source` | 命中来源病种(如 `肺癌`、`纵隔肿瘤`、`食管癌`、`气管疾病`、`第五类`) |
| `title` / `journal` / `pubdate` | 文献元数据 |
| `reason` | 中文一句话排除理由(LLM 输出) |

> 注:`excluded_records` **不暴露 UI**,仅 `/api/changelog` 返回当日 `excluded_count` 汇总数字;明细留存 SQLite 供后续审核。

---

## 六、PubMed 检索工具与方法

PubMed 检索的事实标准接口是 **NCBI E-utilities** HTTP API。下游可自行处理格式化输出(JSON、表格、Markdown 报告等)。

### 6.1 核心工具:NCBI E-utilities

| 端点 | URL | 用途 | 响应格式 |
|---|---|---|---|
| `esearch.fcgi` | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi` | 按检索式返回 PMID 列表 | JSON / XML |
| `efetch.fcgi` | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi` | 按 PMID 抓取文章元数据与摘要 | XML |

#### esearch 关键请求参数

| 参数 | 值 | 说明 |
|---|---|---|
| `db` | `pubmed` | 固定 |
| `term` | 完整检索式字符串 | 见第四节模板 |
| `retmode` | `json`(推荐)/ `xml` | 响应格式 |
| `retmax` | `500`(建议上限) | 单次返回 PMID 上限 |
| `sort` | `pub date` | 按发表日期排序 |
| `api_key` | 可选 | 提高速率上限 |

#### efetch 关键请求参数

| 参数 | 值 | 说明 |
|---|---|---|
| `db` | `pubmed` | 固定 |
| `id` | PMID 列表(逗号分隔) | 推荐每 200 个一批,**>200 UID 须 POST** |
| `retmode` | `xml` | 推荐用 `ElementTree` 解析 |
| `api_key` | 可选 | 同上 |

### 6.2 LLM 工具(MiniMax M3,OpenAI 兼容)

| 端点 | URL | 用途 |
|---|---|---|
| `chat/completions` | `https://api.MiniMax.chat/v1/chat/completions` | LLM 分类 + 中英翻译 |

请求参数:
| 参数 | 值 | 说明 |
|---|---|---|
| `model` | `MiniMax-M3` | 固定 |
| `messages` | `[{role:system,...},{role:user,...}]` | system 含分类规则,user 含本批 10 篇 |
| `response_format` | `{"type":"json_object"}` | 强制 JSON 输出 |
| `temperature` | `0.2` | 低温度稳定输出 |
| `Authorization` | `Bearer ${LLM_API_KEY}` | 用户提供 |

### 6.3 速率限制

| 接口 | 无 API key | 有 API key |
|---|---|---|
| NCBI E-utilities | 3 req/s(sleep 0.34s) | 10 req/s(sleep 0.1s) |
| MiniMax M3 | (由端点决定,本项目 semaphore=3 + 重试 3 次) | — |

### 6.4 常用依赖(Python)

| 模块 | 用途 |
|---|---|
| `httpx` | async HTTP 调用 E-utilities + MiniMax |
| `json` | 解析 esearch JSON / 读写白名单 / 写出检索 bundle |
| `xml.etree.ElementTree` | 解析 efetch XML,抽取 PMID、标题、作者、单位、期刊、DOI、摘要、PubType、epdat |
| `asyncio` | 5 病种 × 5 chunks 并发抓取 |
| `zoneinfo.ZoneInfo` | Beijing 时区换算 |
| `aiosqlite` | SQLite 异步 ORM |
| `fastapi` / `uvicorn` | 后端 API |
| `pydantic` / `pydantic-settings` | 数据模型与配置 |
| `datetime.date` / `timedelta` | 前一天日期换算 |
| `hashlib` | LLM 缓存键 `hash(pmid)` |
| `argparse` | CLI 参数解析(`backfill --from --to`) |
| `pathlib.Path` | 输出路径与目录创建 |

### 6.5 检索调用流程(参考伪代码)

```python
# Step 0 — 决定目标日
target_date = previous_beijing_day()  # Beijing "昨天"
epdat = f"{target_date}:{target_date}[epdat]"

# Step 1 — 组装每个病种 × 每个期刊 chunk 的检索式
queries = [
    build_query(disease, journal_chunk, epdat)
    for disease in DISEASES        # 5 病种
    for journal_chunk in chunked(JOURNAL_TERMS, 18)  # 114 本 / 18 ≈ 7 chunks
]
# 共 35 条 esearch 查询

# Step 2 — esearch 取 PMID (病种内去重,保留 disease 来源)
pmids_by_disease = await gather_esearch(queries, api_key=api_key)
# 返回: {"lung_cancer": {"12345678", "23456789"}, "esophageal": {"12345678", ...}, ...}

# Step 3 — efetch 抓全文元数据 (每 200 PMID 一批,POST)
all_pmids = sorted(union(pmids_by_disease.values()))
raw_xml_batches = await gather_efetch(all_pmids, batch_size=200, api_key=api_key)
# 每条记录解析为 dict:
# pmid / title / title_zh(null)/ abstract / abstract_zh(null) / authors / affiliations /
# journal / journal_full(null)/ journal_abbr / doi / publication_types / pubdate / epdat

# Step 4 — 解析 + 记录 disease_hint(LLM 兜底用)
records = parse_xml_batches(raw_xml_batches)
for r in records:
    r.disease_hint = first_disease_for_pmid(r.pmid, pmids_by_disease)

# Step 5 — LLM 分类 + 翻译(批 10/次,失败降级)
enriched = await classify_and_translate_batch(records)
# 每条记录被填充: type / disease / llm_excluded / llm_exclude_reason /
#                 title_zh / abstract_zh / llm_classified_at / llm_model / llm_needs_review

# Step 6 — join journal_metrics.json → stamp IF/Q1/新锐
for r in enriched:
    stamp_journal_metrics(r, metrics_index)

# Step 7 — 拆分:publish / exclude
to_publish = [r for r in enriched if not r.llm_excluded]
to_exclude = [r for r in enriched if r.llm_excluded]
upsert_articles(conn, to_publish)
upsert_excluded_records(conn, to_exclude)

# Step 8 — daily_snapshots 元数据
upsert_snapshot(conn, target_date, to_publish, total_fetched=len(records), excluded=len(to_exclude))

# Step 9 — JSON snapshot(Astro 构建期读取)
write_snapshot(target_date, to_publish)

# Step 10 — run_log
log_run(conn, kind='daily', target_date=target_date, status='ok',
        fetched=len(records), classified=len(to_publish), llm_calls=...)
```

### 6.6 输出 bundle 推荐结构(SQLite 6 张表 + JSON snapshot)

**SQLite**(`/data/thoracic.db`):

| 表 | 用途 | 关键字段 |
|---|---|---|
| `articles` | 主文章去重 store | `pmid` PK, `title` / `title_zh` / `abstract` / `abstract_zh` / `authors` / `affiliations` / `journal` / `journal_full` / `journal_abbr` / `doi` / `publication_types` / `pubdate` / `epdat` / `fetched_at` / `disease`(单值) / `type`(单值) / `llm_*` / `impact_factor` / `jcr_quartile` / `new_talent_quartile` / `matched_jcr` |
| `articles_fts` | FTS5 虚表(标题/摘要搜索) | `title` / `title_zh` / `abstract` / `abstract_zh` / `journal_full` |
| `daily_snapshots` | 每日聚合元数据 | `date` PK, `article_count` / `total_fetched` / `excluded_count` / `by_disease_json` / `by_type_json` / `llm_calls` / `llm_cost_usd` |
| `run_log` | 每次抓取运行日志 | `started_at` / `finished_at` / `kind` / `target_date` / `fetched_count` / `classified_count` / `llm_calls` / `status` / `error_msg` |
| `excluded_records` | LLM 排除审计(不暴露 UI) | `pmid` PK, `hit_source` / `title` / `journal` / `pubdate` / `reason` |
| `llm_cache` | LLM 输出缓存(`hash(pmid)` → JSON) | `pmid_hash` PK, `payload_json` / `model` / `created_at` / `expires_at` |

**JSON snapshot**(`/data/snapshots/YYYY-MM-DD.json`):

```jsonc
{
  "date": "2026-07-30",
  "generated_at": "2026-07-31T00:05:23+00:00",
  "article_count": 38,
  "articles": [
    {
      "pmid": "39012345",
      "title": "Microsoft FY2026 Q4 earnings: compute supply still insufficient...",
      "title_zh": "微软件 2026 财年第四财季业绩会实录:算力供给依然不足...",
      "epdat": "2026-07-30",
      "journal": "Lancet",
      "journal_full": "The Lancet",
      "authors": ["Author A", "Author B"],
      "affiliations": ["Affiliation 1", "Affiliation 2"],
      "type": "clinical",
      "disease": "lung_cancer",
      "impact_factor": 109.0,
      "jcr_quartile": "Q1",
      "new_talent_quartile": "1区",
      "publication_types": ["Journal Article", "Multicenter Study"]
    }
  ]
}
```

### 6.7 速率与认证

- **NCBI 无 API key**: 约 3 req/s → 推荐 `await asyncio.sleep(0.34)`
- **NCBI 有 API key**: 约 10 req/s → 推荐 `await asyncio.sleep(0.10)`
- 获取 NCBI key:`https://www.ncbi.nlm.nih.gov/account/settings/`
- 携带方式:把 key 作为 `api_key=...` 传入 `esearch` / `efetch`
- **MiniMax M3**:用户自带 API Key,配置在 `.env` 的 `LLM_API_KEY`,本项目 `semaphore=3` + 重试 3 次(指数退避)

### 6.8 调试与排错技巧

| 现象 | 建议 |
|---|---|
| 想确认检索式是否符合预期,不想触发 API | 用 curl / Postman 先打单条 esearch;或先无 key 小流量试探 |
| 某个期刊 chunk 触发 URL 超长 / 5xx | chunk 大小降到 1,定位罪魁期刊词 |
| 想复现某一天的检索(测试场景) | 用覆盖"今天"的日期,使 `previous_beijing_day` 落到预期窗口 |
| 单次返回太多,失败重试成本高 | 把 `retmax` 调小(如 50) |
| 某病种 0 命中 | 放宽到宽泛的纵隔/胸腺检索,再人工筛选;不得自动并入 |
| LLM 报 429 / 5xx | 重试 + 退避;若持续,降级到 PubType 启发式 |
| LLM 返回非 JSON | 用 json_parse 修复策略(strip `<think>...</think>` + 提取首个 `{...}` 块);3 次失败后降级 |

---

## 七、定时调度(cron)

### 7.1 推荐方案

- **容器内 supercronic**(二进制,~7MB)+ Docker Compose,自动重启
- 不依赖 host cron / GitHub Actions(独立可观测)

### 7.2 crontab 内容

```cron
# 北京时间 8:00 抓取前一天(UTC 0:00)
0 0 * * * cd /app && python -m thoracic.pipeline.daily --target $(TZ=Asia/Shanghai date -d 'yesterday' +%Y-%m-%d) >> /var/log/cron.log 2>&1

# 每周一 10:00 北京时间清理 180 天前 snapshot JSON(保留 SQLite 全部)
0 2 * * 1 cd /app && python -m thoracic.pipeline.cleanup --older-than 180 >> /var/log/cron.log 2>&1
```

`TZ=Asia/Shanghai date -d 'yesterday'` 强制按 Beijing 时区计算前一天,避免容器时区漂移。

### 7.3 手动回填 CLI

```bash
# 首次回填 11 天(并发 3)
python -m thoracic.pipeline.backfill --from 2026-07-20 --to 2026-07-30 --concurrency 3

# 仅回填单日
python -m thoracic.pipeline.backfill --from 2026-07-29 --to 2026-07-29

# Dry-run(不入库,仅打印统计)
python -m thoracic.pipeline.backfill --from 2026-07-30 --to 2026-07-30 --dry-run
```

---

## 八、关键 PubMed 字段速查

| 字段 | 出处 | 用途 |
|---|---|---|
| `[edat]` | PubMed 字段 | PubMed 入库日(Entrez Date,本规则唯一时间字段) |
| `[Mesh]` | PubMed MeSH | 受控词检索(默认 explosion) |
| `[Mesh:noexp]` | PubMed MeSH | 受控词检索(不展开 narrower terms) |
| `[Mesh Major Topic]` / `[majr]` | PubMed MeSH | 主要论题(带 `*` 标记的主题) |
| `[tiab]` / `[Title/Abstract]` | PubMed 字段 | 标题+摘要自由词检索 |
| `[tw]` / `[Text Word]` | PubMed 字段 | 标题+摘要+MeSH+副主题词(最宽) |
| `[jour]` | PubMed 字段 | 期刊限定,白名单使用 |
| `[la]` | PubMed 字段 | 语言限定(如 `english[la]`、`chinese[la]`) |

---

## 九、不变量(项目铁律)

1. **`[edat]`(PubMed 入库日)唯一时间字段**,禁止使用 `[dp]` / `[pdat]` / `[epdat]` / `reldate`
2. **每日单日区间**,禁止周/月区间检索(除非显式覆盖)
3. **5 病种 × 5 研究类型 = 25 组合**,不增不减
4. **单归属**:每篇 1 个 `type` + 1 个 `disease`,LLM 强制单选
5. **LLM 必须**:每条新文献过 MiniMax M3 分类 + 翻译
6. **LLM 失败降级**:PubType 启发式兜底,`llm_needs_review=1` 标记
7. **`excluded_records` 不暴露 UI**,仅 SQLite 留存 + `/api/changelog` 汇总
8. **期刊白名单**:`journal_metrics.json` 114 本 138 词
9. **不在检索式内嵌 `[la]`**:不限定语言(英文为主但不强制)
10. **纵隔补检**:严格命中为 0 才放宽;放宽结果标记 `needs_review`,不自动并入

---

## 十、版本与修订

| 版本 | 日期 | 修订要点 |
|---|---|---|
| v1 | 2026-07-29 | 初版(4 病种 × 3 研究类型,周报模式) |
| v2 | 2026-07-31 | 改为每日监控;5 病种 + 5 研究类型;单归属;LLM 辅助;MiniMax M3 |
| 当前 | — | 与 `PLAN.md` v4 一致 |

— 文档与 `PLAN.md` v4 同步;若 plan 修订,本文档必须同步更新。