from __future__ import annotations
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def default_metrics_path() -> Path:
    """白名单文件路径。容器内 site-packages 的相对定位不可靠,用环境变量覆盖。"""
    env = os.environ.get("THORACIC_METRICS_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[4] / "journal_metrics.json"


def load_journal_terms(path: str | None = None) -> list[str]:
    """读 `journal_metrics.json`,返回所有 `pubmed_journal_terms` 展平去重列表。

    JSON 结构:`{"metadata": {...}, "journals": [{journal, pubmed_journal_terms, ...}, ...]}`
    """
    p = Path(path) if path else default_metrics_path()
    if not p.is_file():
        # 空白名单会让每日检索静默返回 0 篇,必须留下痕迹。
        log.warning(f"journal_metrics.json not found at {p}; journal whitelist is empty")
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    journals = data.get("journals") if isinstance(data, dict) else data
    if not isinstance(journals, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in journals:
        if not isinstance(item, dict):
            continue
        for term in item.get("pubmed_journal_terms") or []:
            cleaned = term.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                out.append(cleaned)
    return out


def chunk_journal_terms(terms: list[str], size: int = 18) -> list[list[str]]:
    if size <= 0:
        raise ValueError("size must be positive")
    return [terms[i : i + size] for i in range(0, len(terms), size)]
