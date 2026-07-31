"""Thoracic literature pipeline (daily fetch, backfill, cleanup).

Phase A 第 6 步(pipeline)交付:
- ``daily.run_daily`` — 单日抓取 → LLM 分类翻译 → 入库 → JSON snapshot
- ``backfill.run_backfill`` — 多日回填
- ``cleanup.cleanup_old_snapshots`` — 清理老 snapshot JSON
- ``journal_stamp`` — 期刊指标 stamp
"""
