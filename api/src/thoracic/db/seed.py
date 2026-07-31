"""期刊白名单索引(`journal_metrics.json` → 内存 lookup)。

设计:
- 维护三类索引:
  - `by_journal`: 期刊全称小写 → metrics
  - `by_term`: 任意 pubmed_journal_term 小写 → metrics
  - `fuzzy_list`: 按 term 长度倒序的 (term, metrics),contains 匹配
- `lookup(journal_term)`: 三级回退
  1) `by_journal` 精确匹配(全称小写)
  2) `by_term` 精确匹配
  3) `fuzzy_list` 顺序 contains(最长 term 优先)
- `__main__` 块演示索引大小与若干 lookup。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class JournalMetrics:
    """单本期刊的 JCR / 新锐分区指标。"""

    journal: str
    impact_factor: float | None
    jcr_quartile: str | None
    new_talent_quartile: str | None
    categories: str | None
    matched_jcr_journal: str | None
    pubmed_journal_terms: tuple[str, ...]


@dataclass
class JournalIndex:
    """三级回退的期刊查找索引。"""

    by_journal: dict[str, JournalMetrics] = field(default_factory=dict)
    by_term: dict[str, JournalMetrics] = field(default_factory=dict)
    fuzzy_list: list[tuple[str, JournalMetrics]] = field(default_factory=list)

    def lookup(self, journal_term: str | None) -> JournalMetrics | None:
        """三级回退查询;`journal_term` 为 None / 空串时返回 None。"""
        if not journal_term:
            return None
        key = journal_term.strip().lower()

        # 1) 精确 by_journal
        hit = self.by_journal.get(key)
        if hit is not None:
            return hit

        # 2) 精确 by_term
        hit = self.by_term.get(key)
        if hit is not None:
            return hit

        # 3) 前缀模糊:key 或 term 是对方的开头
        #    然后按 "key 与 term 的长度差" 升序选最接近的
        #    (避免 "lancet" 命中 "the lancet oncology" 这种过度前缀)
        candidates: list[tuple[int, JournalMetrics]] = []
        for term, metrics in self.fuzzy_list:
            if key.startswith(term) or term.startswith(key):
                candidates.append((abs(len(term) - len(key)), metrics))
        if candidates:
            candidates.sort(key=lambda x: (x[0], -1))  # 长度差最小优先
            return candidates[0][1]
        return None


def default_path() -> str:
    """默认从 `references/journal_metrics.json` 读取;支持 `THORACIC_ROOT` 覆盖。

    当前项目根(非容器)的白名单文件在 `journal_metrics.json`(根目录),
    若 `THORACIC_ROOT` 设置则从 `<THORACIC_ROOT>/references/journal_metrics.json` 读取。
    """
    env = os.environ.get("THORACIC_ROOT")
    if env:
        return str(Path(env) / "references" / "journal_metrics.json")
    # 优先根目录版本(与 references/ 内容一致,任一存在即可)
    project_root = Path(__file__).resolve()
    for _ in range(6):  # 最多向上 6 层,适配 src/thoracic/db/seed.py
        candidate_root = project_root / "journal_metrics.json"
        candidate_refs = project_root / "references" / "journal_metrics.json"
        if candidate_refs.is_file():
            return str(candidate_refs)
        if candidate_root.is_file():
            return str(candidate_root)
        project_root = project_root.parent
    # 找不到时返回根目录默认路径(由 caller 处理 FileNotFoundError)
    return "journal_metrics.json"


def _normalize_terms(terms: Iterable[str]) -> tuple[str, ...]:
    """PubMed 期刊词去空 / 去重,保持顺序。"""
    seen: set[str] = set()
    out: list[str] = []
    for term in terms or ():
        cleaned = term.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            out.append(cleaned)
    return tuple(out)


def _build_metrics(record: dict) -> JournalMetrics:
    """单条 journal 字典 → JournalMetrics。"""
    return JournalMetrics(
        journal=record.get("journal", "").strip(),
        impact_factor=record.get("impact_factor"),
        jcr_quartile=record.get("jcr_quartile"),
        new_talent_quartile=record.get("new_talent_quartile"),
        categories=record.get("categories"),
        matched_jcr_journal=record.get("matched_jcr_journal"),
        pubmed_journal_terms=_normalize_terms(record.get("pubmed_journal_terms", [])),
    )


def build_journal_index(metrics_json_path: str | None = None) -> JournalIndex:
    """从 JSON 文件构建索引。`metrics_json_path` 为空时用 `default_path()`。"""
    path = Path(metrics_json_path or default_path())
    data = json.loads(path.read_text(encoding="utf-8"))
    journals = data.get("journals", [])

    index = JournalIndex()

    for record in journals:
        metrics = _build_metrics(record)
        if not metrics.journal:
            continue
        index.by_journal[metrics.journal.lower()] = metrics
        for term in metrics.pubmed_journal_terms:
            index.by_term.setdefault(term.lower(), metrics)

    # 模糊列表:按 term 长度倒序,优先匹配最长
    pairs: list[tuple[str, JournalMetrics]] = []
    for metrics in index.by_journal.values():
        for term in metrics.pubmed_journal_terms:
            pairs.append((term.lower(), metrics))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    index.fuzzy_list = pairs

    return index


if __name__ == "__main__":  # pragma: no cover - CLI demo
    import sys

    path = default_path()
    if len(sys.argv) > 1:
        path = sys.argv[1]
    try:
        idx = build_journal_index(path)
    except FileNotFoundError:
        print(f"ERROR: journal_metrics.json not found at {path}", file=sys.stderr)
        sys.exit(1)

    print(f"Index loaded from: {path}")
    print(f"  by_journal entries: {len(idx.by_journal)}")
    print(f"  by_term entries:    {len(idx.by_term)}")
    print(f"  fuzzy_list length:  {len(idx.fuzzy_list)}")

    probes = [
        "Lancet",
        "Lancet Oncol",
        "Annals of Thoracic Surgery",
        "胸外科未知期刊",  # noqa: 中文不命中,演示未匹配场景
        "Random Not Exist Journal",
    ]
    for term in probes:
        hit = idx.lookup(term)
        if hit is None:
            print(f"  lookup({term!r}) -> None")
        else:
            print(
                f"  lookup({term!r}) -> {hit.journal!r} "
                f"(IF={hit.impact_factor}, JCR={hit.jcr_quartile}, "
                f"新锐={hit.new_talent_quartile})"
            )
