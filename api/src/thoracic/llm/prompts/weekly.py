"""周报综述的 LLM prompt:按「病种 × 研究类型」组织中文综述段。

供周报 pipeline 复用:每个(病种 × 类型)调用一次 chat_json,输入该类型带全局
ref_no 的文章列表,输出该类型一段 summary(正文用 [n] 引用参考文献)。
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
1. `type` 只能是输入文章里实际出现的类型 slug(clinical / ai_ml / basic_research / review / guideline)。输入中出现的**每一个**类型都必须输出一个 subsection,**一个都不能漏**;每个类型只输出一段;输入里没有的类型不要输出。
2. 每个 `summary` 是 4~8 句、约 200~350 字的中文综述(该类型文献篇数多时可更长)。要写成有信息量的综述段,而不是一句结论。对**每一篇**文章都尽量展开写,至少涵盖以下要素:研究设计(前瞻/回顾队列、随机对照试验、荟萃分析、系统综述、基础实验等)、人群与样本量、干预与对照、主要终点、关键结果(尽量给出具体数值、效应量或置信区间,如「OR 1.8,95%CI 1.2-2.7」「5 年生存率 68% vs 54%」)、以及临床或方法学意义。不要只写一句结论,不要停留在题名层面,不要逐篇罗列题名。
3. **引用编号是硬性要求**:每个 summary 必须用 [n] 引用该类型下**每一篇**文章的编号,每篇至少出现一次;例如该类型有 3 篇、编号为 [5][6][7],则 summary 中必须同时出现 [5]、[6] 和 [7],一篇都不能漏。某类型只有一篇文章时,也必须在 summary 中引用其编号。编号只能来自输入文章,不得虚构或越界。
4. 引用只标对应类型文章的编号。
5. 客观、克制,不夸大、不编造;数据未报告时写「未报告」即可。
6. 只输出 JSON,不要多余说明。

合格输出示例(输入该类型有 3 篇,编号 [5][6][7]):
{
  "subsections": [
    {"type": "clinical", "summary": "本周 3 项临床研究[5][6][7]分别从围术期干预、新辅助治疗与术后管理三个角度更新了肺癌外科的证据。[5]为单中心回顾性队列,纳入 120 例 I-IIIA 期非小细胞肺癌患者,比较胸腔镜与开放肺叶切除术的近期结局,结果显示胸腔镜组术后住院时间更短(5.2 vs 7.8 天)、30 天并发症发生率更低(18% vs 31%),但两组 3 年无病生存率差异无统计学意义(HR 0.92,95%CI 0.71-1.19),提示微创术式短期获益显著、长期肿瘤学结局相当。[6]报告了一项 II 期随机对照试验,比较新辅助免疫联合化疗(纳武利尤单抗+含铂双药)与单纯化疗用于可切除非小细胞肺癌,主要终点病理完全缓解率在联合组显著更高(32.4% vs 8.2%,p<0.001),R0 切除率亦更优,为该方案的围术期应用提供了随机对照层面的证据,但长期生存获益仍需更大样本随访确认。[7]为多中心前瞻性队列,纳入 210 例术后患者,验证了基于胸腔引流液 IL-6 动态监测对术后肺部感染的预测价值(敏感性 82%、特异性 76%),提示生物标志物驱动的监测有望减少漏诊并指导抗生素合理使用。综合来看[5][6][7],微创手术与围术期综合管理持续改善肺癌外科的近期结局,新辅助免疫的病理缓解获益已有随机对照证据,但长期生存与成本效益仍有待更多随访数据回答。"}
  ]
}"""


def build_user_payload(
    disease_zh: str, articles: list[dict], *, type_zh: str | None = None
) -> str:
    """把带 ref_no 的文章拼成可读字符串(给 user 消息)。

    articles 每个 dict 建议字段:ref_no / type_zh / title_zh / journal_full / pubdate / abstract_zh。
    摘要需在调用前截断(约 300 字),避免超出上下文。

    传 `type_zh` 时按「病种 × 类型」单类型调用构造:首行标注类型,并要求 LLM 只输出
    该类型的一个综述段(配合 pipeline 里逐类型各调一次 LLM 的 `_summarize_disease`)。
    """

    if type_zh:
        header = (
            f"病种:{disease_zh} · 类型:{type_zh},共 {len(articles)} 篇。"
            "每篇格式为「[编号] (类型) 中文题名 / 期刊与日期 / 摘要节选」。"
            f"请只针对「{type_zh}」这一个类型输出一个综述段,不要输出其他类型。"
        )
    else:
        header = (
            f"病种:{disease_zh},本周共 {len(articles)} 篇。"
            "每篇格式为「[编号] (类型) 中文题名 / 期刊与日期 / 摘要节选」。"
        )
    lines = [
        header,
        "注意:综述 summary 必须用 [编号] 引用该类型下每一篇文章,每篇至少一次;"
        "例如该类型 3 篇编号为 [5][6][7] 时,summary 中必须出现 [5]、[6]、[7]。",
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
