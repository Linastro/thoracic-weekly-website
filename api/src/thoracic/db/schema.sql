-- ============================================================
-- Thoracic Literature Daily Monitor - SQLite Schema v2
-- 6 tables: articles / daily_snapshots / run_log / excluded_records / llm_cache + articles_fts (virtual)
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- 主表:每条 PubMed 文献
CREATE TABLE IF NOT EXISTS articles (
    pmid              TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    title_zh          TEXT NOT NULL,
    abstract          TEXT,
    abstract_zh       TEXT,
    authors           TEXT NOT NULL,            -- JSON array
    affiliations      TEXT,                     -- JSON array
    journal           TEXT NOT NULL,
    journal_full      TEXT,
    journal_abbr      TEXT,
    doi               TEXT,
    publication_types TEXT NOT NULL,            -- JSON array
    pubdate           TEXT,
    epdat             TEXT NOT NULL,
    fetched_at        TEXT NOT NULL,

    -- 单归属 1:1
    disease           TEXT NOT NULL,
    type              TEXT NOT NULL,

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

CREATE INDEX IF NOT EXISTS idx_articles_epdat ON articles(epdat);
CREATE INDEX IF NOT EXISTS idx_articles_disease ON articles(disease);
CREATE INDEX IF NOT EXISTS idx_articles_type ON articles(type);
CREATE INDEX IF NOT EXISTS idx_articles_journal ON articles(journal);
CREATE INDEX IF NOT EXISTS idx_articles_excluded ON articles(llm_excluded);

-- 每日快照元数据
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

-- FTS5 虚表
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

-- 运行日志
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

-- LLM 排除审计
CREATE TABLE IF NOT EXISTS excluded_records (
    pmid          TEXT PRIMARY KEY,
    hit_source    TEXT,
    title         TEXT,
    journal       TEXT,
    pubdate       TEXT,
    reason        TEXT NOT NULL
);

-- LLM 输出缓存
CREATE TABLE IF NOT EXISTS llm_cache (
    pmid_hash      TEXT PRIMARY KEY,
    payload_json   TEXT NOT NULL,
    model          TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    expires_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_cache_expires ON llm_cache(expires_at);
