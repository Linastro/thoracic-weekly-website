# Thoracic Weekly · 胸外文献每日监控站

> PubMed 胸外文献每日监控:PubMed 抓取 → LLM(DeepSeek)分类翻译 → SQLite → snapshot JSON → Astro 静态站。
>
> 线上地址:**https://www.thoracic-linastro.com.cn** ｜ 开源仓库:https://github.com/Linastro/thoracic-weekly-website

## 简介

每天北京时间 14:00,自动从 PubMed 按入库日 `[edat]` 抓取前一个完整入库日的 **5 大病种 × 5 类研究类型** 胸外文献,经大语言模型做单归属分类与中英翻译,持久化到 SQLite,并以卡片化静态网站展示。每周一 19:00 再自动把上一自然周(周一~周日)已入库文献总结成按「病种 × 类型」的中文周报(正文带引用 + 底部英文参考文献)。

### 覆盖范围

- **5 大病种**:肺癌、食管癌、纵隔肿瘤、气管疾病、气胸·外伤·胸壁
- **5 类研究类型**:临床研究、AI/ML 研究、基础研究、综述与 Meta 分析、指南与共识
- **期刊白名单**:仅收录 `journal_metrics.json` 中 114 本高影响力胸外相关期刊

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12 + FastAPI + SQLite(FTS5) |
| 数据源 | PubMed E-utilities |
| LLM | DeepSeek(OpenAI 兼容接口) |
| 前端 | Astro 4 + React + TypeScript |
| 部署 | Docker + Nginx + Caddy(HTTPS/域名) |

## 本地运行

```bash
# 后端(必须显式给 PYTHONPATH 与两个路径变量,否则读不到包和数据)
PYTHONPATH=api/src DB_PATH=/tmp/thoracic-data/thoracic.db SNAPSHOT_DIR=/tmp/thoracic-data/snapshots \
  .venv/bin/uvicorn thoracic.main:app --port 8080

# 前端 dev(vite proxy /api → 8080)
cd web && npm run dev   # http://localhost:4321

# 前端类型检查(项目唯一类型检查)
cd web && npm run check
```

环境变量模板见 `.env.example`。

## 项目结构

```
api/                  # FastAPI 后端(pipeline / db / llm / snapshots / scripts)
cron/                 # 定时脚本与 crontab(daily.sh / weekly.sh / cleanup.sh)
web/                  # Astro 前端(静态站)
journal_metrics.json  # 期刊白名单(IF / JCR 分区)
docker-compose.yml    # 三容器 api / cron / web,前置 Caddy 做 HTTPS
```

## 数据流

```
PubMed([edat] 入库日) → LLM 分类/翻译 → SQLite → snapshot JSON → Astro 静态站
```

- 每日任务:`cron/cron_jobs/daily.sh`(北京 14:00,单日 `[edat]`)
- 周报任务:`cron/cron_jobs/weekly.sh`(周一 19:00)
- 清理任务:`cron/cron_jobs/cleanup.sh`(周一 10:00,删 180 天前 snapshot)

更详细的架构约束、部署流程与踩坑记录见 `CLAUDE.md` 与 `HANDOFF.md`(后者含服务器信息,未纳入 git)。
