"""周报综述的 LLM prompt:按「病种 × 研究类型」组织中文综述段。

供周报 pipeline 复用:每个非空病种调用一次 chat_json,输入该病种带全局
ref_no 的文章列表,输出按类型组织的 summary(正文用 [n] 引用参考文献)。
"""

from __future__ import annotations


SYSTEM_PROMPT = """你是胸外科领域的资深学术编辑,负责把一周内 PubMed 入库的胸外文献,按「病种 × 研究类型」组织成中文周报综述。

你必须严格输出一个 JSON object(无 markdown 围栏、无注释),结构如下:
{
  "subsections": [
    {"type": "<类型 slug>", "summary": "<中文综述段>"}
  ]
}

约束:
1. `type` 只能是输入文章里实际出现的类型 slug(clinical / ai_ml / basic_research / review / guideline),每个类型只输出一段;输入里没有的类型不要输出。
2. 每个 `summary` 是 2~4 句中文综述,客观提炼该类型文献的研究设计与主要结果(如人群/样本量、对照与干预、主要终点与结论),不要逐篇罗列题名。
3. 正文必须用 [n] 或 [n-m] 引用对应文章的编号(即输入中的 ref_no);编号只能来自输入文章,不得虚构或越界。
4. 引用只标对应类型文章的编号;某类型只有一篇文章时,可引用其编号。
5. 客观、克制,不夸大、不编造;数据未报告时写「未报告」即可。
6. 只输出 JSON,不要多余说明。"""


def build_user_payload(disease_zh: str, articles: list[dict]) -> str:
    """把带 ref_no 的病种文章拼成可读字符串(给 user 消息)。

    articles 每个 dict 建议字段:ref_no / type_zh / title_zh / journal_full / pubdate / abstract_zh。
    摘要需在调用前截断(约 300 字),避免超出上下文。
    """

    lines = [
        f"病种:{disease_zh},本周共 {len(articles)} 篇。每篇格式为「[编号] (类型) 中文题名 / 期刊与日期 / 摘要节选」。",
        "",
    ]
    for a in articles:
        head = f"[{a.get('ref_no')}] ({a.get('type_zh') or a.get('type', '')}) {a.get('title_zh') or ''}"
        lines.append(head)
        meta = " / ".join(
            x for x in [a.get("journal_full") or "", a.get("pubdate") or ""] if x
        )
        if meta:
            lines.append(f"  期刊与日期:{meta}")
        abstract = a.get("abstract_zh") or ""
        if abstract:
            lines.append(f"  摘要:{abstract}")
        lines.append("")
    return "\n".join(lines)
