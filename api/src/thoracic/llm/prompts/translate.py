"""独立翻译 prompt(可选备用)。

主流程(classify_and_translate_batch)会合并使用 `classify.py` 中的合并 prompt;
本模块保留独立翻译函数,便于:
- 仅重翻译已分类文章的标题/摘要
- 单篇调式 / v2 后续编辑场景
"""

from __future__ import annotations

import json


SYSTEM_PROMPT = """你是医学文献翻译助手。将英文标题与摘要翻译为简洁、自然的中文。
- 保留所有专有名词(药名、基因、菌种、人名、机构名)原英文
- 普通描述性文字用简洁中文
- 输出严格 JSON,无 markdown 围栏:{"title_zh":"...","abstract_zh":"..."}
"""


def build_user_payload(records: list[dict]) -> str:
    """输入:每条记录必须有 pmid / title / abstract。"""
    return json.dumps(
        [
            {
                "pmid": r["pmid"],
                "title": r.get("title", ""),
                "abstract": r.get("abstract") or "",
            }
            for r in records
        ],
        ensure_ascii=False,
        indent=2,
    )
