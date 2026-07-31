from __future__ import annotations
import json
from pathlib import Path


def load_journal_terms(path: str | None = None) -> list[str]:
    """读 `journal_metrics.json`,返回所有 `pubmed_journal_terms` 展平去重列表。

    JSON 结构:`{"metadata": {...}, "journals": [{journal, pubmed_journal_terms, ...}, ...]}`
    """
    p = Path(path) if path else Path(__file__).resolve().parents[4] / "journal_metrics.json"
    if not p.is_file():
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
