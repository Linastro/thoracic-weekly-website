"""LLM 分类与翻译的 system prompt(单次合并调用)。"""

from __future__ import annotations

import json


SYSTEM_PROMPT = """你是胸外科文献分类与翻译助手。对每篇 PubMed 文献,你必须严格输出 JSON object(无 markdown 围栏,无注释):

{
  "items": [
    {
      "pmid": "<字符串>",
      "type": "clinical" | "ai_ml" | "basic_research" | "review" | "guideline",
      "disease": "lung_cancer" | "esophageal" | "mediastinal" | "tracheal" | "chest_wall_injury",
      "exclude": false,
      "exclude_reason": null,
      "title_zh": "<中文标题,自然流畅,保留专有名词原英文>",
      "abstract_zh": "<中文摘要,自然流畅,保留医学术语与原英文>"
    }
  ]
}

字段约束:
1. `type`:5 选 1 — clinical(临床研究)/ ai_ml(AI/ML 研究)/ basic_research(基础研究)/ review(综述与 Meta)/ guideline(指南与共识)
2. `disease`:5 选 1 — lung_cancer(肺癌)/ esophageal(食管癌)/ mediastinal(纵隔肿瘤)/ tracheal(气管疾病)/ chest_wall_injury(气胸·胸外伤·肋骨骨折·胸壁畸形)
3. 每篇文献在多 PubType 或多病种命中时,只输出最准确的 1 个。
4. `exclude = true` 时:主病种不属于 5 大病种,或为 letter/news/editorial/abstract-only/仅附带提及。
5. 翻译规则:医学术语、药名、基因、菌种、人名等专有名词保持原英文;普通描述性文字翻译为简洁中文。
"""


def build_user_payload(records: list[dict]) -> str:
    """组装 user 消息的 JSON 载荷(输入给 LLM 的 10 条 records 列表)。

    每条记录只暴露 LLM 决策所必需的字段:pmid / title / abstract / publication_types。
    """

    payload = []
    for r in records:
        payload.append(
            {
                "pmid": r.get("pmid", ""),
                "title": r.get("title", ""),
                "abstract": r.get("abstract") or "",
                "publication_types": r.get("publication_types", []),
            }
        )
    return json.dumps(payload, ensure_ascii=False, indent=2)
