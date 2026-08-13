"""周报 pipeline:把一周已入库(epdat 区间)的胸外文献组织成「病种 × 研究类型」中文综述。

流程:校验区间 → 查库 → 全局编号+分组(纯代码,不靠 LLM)→ 逐病种、逐类型各调
一次 LLM 综述 → 组装 payload → 写 `SNAPSHOT_DIR/weekly/{week_start}-{week_end}.json`。

分组/编号顺序常量写死在本文件(与前端 web/src/lib/types.ts 一致)。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from thoracic.db import repo
from thoracic.db.connection import get_db, close_db, init_db
from thoracic.llm.client import default_client
from thoracic.llm.prompts.weekly import SYSTEM_PROMPT, build_user_payload
from ..snapshots.writer import write_weekly_report

log = logging.getLogger(__name__)

# 病种顺序(固定):用于全局编号与 sections 展示顺序
DISEASES = [
    ("lung_cancer", "肺癌"),
    ("esophageal", "食管癌"),
    ("mediastinal", "纵隔肿瘤"),
    ("tracheal", "气管疾病"),
    ("chest_wall_injury", "气胸·外伤·胸壁"),
]
DISEASE_ORDER = {slug: i for i, (slug, _) in enumerate(DISEASES)}

# 研究类型顺序(固定)
TYPES = [
    ("clinical", "临床研究"),
    ("ai_ml", "AI/ML"),
    ("basic_research", "基础研究"),
    ("review", "综述Meta"),
    ("guideline", "指南共识"),
]
TYPE_ORDER = {slug: i for i, (slug, _) in enumerate(TYPES)}


def _neg_epdat(epdat: str) -> int:
    """把 'YYYY-MM-DD' 转成可反序排序的负整数(数值越小日期越晚)。"""
    y, m, d = epdat.split("-")
    return -(int(y) * 10000 + int(m) * 100 + int(d))


def _assign_refs(articles: list[dict]) -> list[dict]:
    """按「病种顺序 → 类型顺序 → epdat 倒序 → pmid」分配全局 ref_no(1..N)。"""
    ordered = sorted(
        articles,
        key=lambda a: (
            DISEASE_ORDER[a["disease"]],
            TYPE_ORDER[a["type"]],
            _neg_epdat(a["epdat"]),
            a["pmid"],
        ),
    )
    for i, a in enumerate(ordered, 1):
        a["ref_no"] = i
    return ordered


def _build_sections(ordered: list[dict]) -> list[dict]:
    """按固定病种顺序构建非空病种节;节内按固定类型顺序保留非空类型。

    返回的 section 带私有 `_articles` 字段(挂在每个 subsection 上),
    供后续 LLM 调用与占位文案统计篇数;最终序列化时丢弃。
    """
    sections: list[dict] = []
    for dslug, dzh in DISEASES:
        disease_articles = [a for a in ordered if a["disease"] == dslug]
        if not disease_articles:
            continue
        subsections: list[dict] = []
        for tslug, tzh in TYPES:
            type_articles = [a for a in disease_articles if a["type"] == tslug]
            if not type_articles:
                continue
            subsections.append(
                {
                    "type": tslug,
                    "type_zh": tzh,
                    "summary": "",
                    "_articles": type_articles,
                }
            )
        sections.append(
            {
                "disease": dslug,
                "disease_zh": dzh,
                "article_count": len(disease_articles),
                "subsections": subsections,
            }
        )
    return sections


def _fallback_summary(sub: dict) -> str:
    """确定性兜底 summary:逐篇列中文题名 + [ref_no],保证非空且带引用。

    不依赖 LLM:LLM 调用失败、漏掉某类型或 summary 为空时,用它代替裸占位文案。
    """
    articles = sub["_articles"]
    items = ";".join(
        f"[{a['ref_no']}] {a.get('title_zh') or ''}" for a in articles
    )
    return f"本周{sub['type_zh']}新增 {len(articles)} 篇:{items}"


def _collapse_citations(text: str) -> str:
    """把相邻且编号连续的 [n][n+1]... 折叠成 [n-m]。

    只折叠「紧邻、中间无任何字符」且编号逐一连续(差值恰为 1)的引用串:
    - [1][2][3][4]    → [1-4]
    - [1][2][3][5][6] → [1-3][5-6](不连续处断开)
    - [1][3]           → [1][3](相邻但不连续,保留原样)
    - 单个 [n]、中间隔文字/空格的保持原样。
    """

    def _fold(m: re.Match[str]) -> str:
        nums = [int(x) for x in re.findall(r"\d+", m.group(0))]
        parts: list[str] = []
        start = prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
                continue
            parts.append(f"[{start}]" if start == prev else f"[{start}-{prev}]")
            start = prev = n
        parts.append(f"[{start}]" if start == prev else f"[{start}-{prev}]")
        return "".join(parts)

    return re.sub(r"(?:\[\d+\]){2,}", _fold, text)


def _ensure_citations(sub: dict, summary: str) -> str:
    """保证每个类型段落的 summary 非空且带 [n] 引用,不依赖 LLM 自觉。

    - summary 缺失/为空 → 确定性兜底(逐篇列题名 + [编号])。
    - summary 非空但无任何 [数字] 引用 → 末尾追加该类型全部编号。
    - 已带引用 → 原样保留。

    最终返回值统一过 `_collapse_citations`,把相邻且连续的编号堆叠折叠成范围,
    保证输出到 JSON 的 summary 里不出现 [1][2][3]... 逐个连排。
    """
    if not summary:
        return _fallback_summary(sub)
    ref_nos = sorted(a["ref_no"] for a in sub["_articles"])
    if not re.search(r"\[\d+", summary):
        summary = f"{summary} " + "".join(f"[{r}]" for r in ref_nos)
    return _collapse_citations(summary)


def _build_llm_payload(disease_articles: list[dict]) -> list[dict]:
    """把病种文章转成 LLM payload;摘要截断 ~300 字,避免超出上下文。"""
    type_zh_by_slug = dict(TYPES)
    payload = []
    for a in disease_articles:
        payload.append(
            {
                "ref_no": a["ref_no"],
                "type_zh": type_zh_by_slug.get(a["type"], a["type"]),
                "title_zh": a.get("title_zh") or "",
                "journal_full": a.get("journal_full") or "",
                "pubdate": a.get("pubdate") or "",
                "abstract_zh": (a.get("abstract_zh") or "")[:300],
            }
        )
    return payload


async def _summarize_disease(sec: dict) -> int:
    """对一个病种按「类型」逐段调 LLM;某类型失败只降级该类型,不整体失败。

    每个(病种 × 类型)各调一次 LLM,每次只喂该类型自己的文章(1~N 篇),
    单次输入与输出都可控,避免大病种(如肺癌单病种 20+ 篇)一次调用被截断
    而退化成逐篇罗列题名。无论 LLM 成功与否,每个类型段 summary 都保证非空
    且带 [n] 引用(走 `_ensure_citations`)。
    返回全部类型成功(1)/存在失败(0)。
    """
    ok = 0
    for sub in sec["subsections"]:
        user = build_user_payload(
            sec["disease_zh"],
            _build_llm_payload(sub["_articles"]),
            type_zh=sub["type_zh"],
        )
        try:
            result = await default_client.chat_json(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
            )
        except Exception as e:  # noqa: BLE001 - 单类型失败只降级该类型,不拖垮整份周报
            log.error(
                f"周报病种 {sec['disease_zh']} 类型 {sub['type_zh']} LLM 调用失败:{e}"
            )
            sub["summary"] = _fallback_summary(sub)
            continue

        # 单类型调用:返回的 subsections 一般只含该类型一项;容错取首个带 summary 的段落。
        summary = ""
        subs = result.get("subsections", []) if isinstance(result, dict) else []
        for s in subs:
            if isinstance(s, dict) and s.get("summary"):
                summary = str(s["summary"])
                break
        sub["summary"] = _ensure_citations(sub, summary)
        ok += 1
    return 1 if ok == len(sec["subsections"]) else 0


def _build_references(ordered: list[dict]) -> list[dict]:
    """参考文献列表由代码从 DB 直接生成,不靠 LLM 编号。"""
    refs = []
    for a in ordered:
        authors = a.get("authors")
        if isinstance(authors, str):
            try:
                authors = json.loads(authors)
            except (ValueError, TypeError):
                authors = []
        refs.append(
            {
                "ref_no": a["ref_no"],
                "pmid": a["pmid"],
                "authors": authors or [],
                "title": a.get("title") or "",
                "journal_full": a.get("journal_full") or "",
                "pubdate": a.get("pubdate"),
                "doi": a.get("doi"),
                "impact_factor": a.get("impact_factor"),
                "jcr_quartile": a.get("jcr_quartile"),
                "new_talent_quartile": a.get("new_talent_quartile"),
            }
        )
    return refs


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


async def run_weekly(
    week_start: str, week_end: str, *, dry_run: bool = False
) -> dict[str, Any]:
    """生成一周胸外文献周报。

    Args:
        week_start: 周起始日 YYYY-MM-DD(闭区间,按 articles.epdat)
        week_end: 周结束日 YYYY-MM-DD
        dry_run: True 时不调 LLM、不写文件,只验证分组+编号

    Returns:
        {"week_start", "week_end", "total_articles", "section_count", "dry_run", "path"}
    """
    # 1. 校验区间
    try:
        start_d = date.fromisoformat(week_start)
        end_d = date.fromisoformat(week_end)
    except ValueError as e:
        raise ValueError(f"日期格式非法,需 YYYY-MM-DD:{e}")
    if end_d < start_d:
        raise ValueError(f"week_end({week_end}) < week_start({week_start})")

    log.info(f"周报 {week_start} ~ {week_end} 开始,dry_run={dry_run}")
    await init_db()
    conn = await get_db()
    try:
        # 2. 查库
        articles = await repo.list_articles_for_week(conn, week_start, week_end)
        total = len(articles)
        if total == 0:
            log.warning(f"周报 {week_start} ~ {week_end} 无已发布文章")

        # 3. 全局编号 + 分组(纯代码)
        ordered = _assign_refs(articles)
        sections = _build_sections(ordered)
        references = _build_references(ordered)

        # 4. 逐病种、逐类型各调一次 LLM(单类型小输入,避免大病种单次调用截断)
        if not dry_run:
            for sec in sections:
                await _summarize_disease(sec)
        else:
            # dry_run:不调 LLM,summary 用确定性兜底(带引用、非空),不写文件
            for sec in sections:
                for sub in sec["subsections"]:
                    sub["summary"] = _fallback_summary(sub)

        # 5. 组装最终 payload(前端契约,务必精确)
        payload = {
            "week_start": week_start,
            "week_end": week_end,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_articles": total,
            "sections": [
                {
                    "disease": sec["disease"],
                    "disease_zh": sec["disease_zh"],
                    "article_count": sec["article_count"],
                    "subsections": [
                        {
                            "type": s["type"],
                            "type_zh": s["type_zh"],
                            "summary": s["summary"],
                        }
                        for s in sec["subsections"]
                    ],
                }
                for sec in sections
            ],
            "references": references,
        }

        # 6. 可选:写 run_log(kind="weekly")
        run_id: int | None = None
        if not dry_run:
            run_id = await repo.write_run_log(
                conn,
                {
                    "started_at": _now_iso(),
                    "finished_at": None,
                    "kind": "weekly",
                    "target_date": f"{week_start}~{week_end}",
                    "fetched_count": total,
                    "classified_count": total,
                    "llm_calls": len(sections),
                    "status": "running",
                    "error_msg": None,
                },
            )
            await conn.commit()

        # 7. 写周报 JSON
        path: str | None = None
        if not dry_run:
            out_path = write_weekly_report(payload)
            path = str(out_path)
            log.info(f"周报 {week_start} ~ {week_end} 已写 {out_path}")
            await repo.update_run_log(
                conn,
                run_id,
                finished_at=_now_iso(),
                status="ok",
                llm_calls=len(sections),
            )
            await conn.commit()

        return {
            "week_start": week_start,
            "week_end": week_end,
            "total_articles": total,
            "section_count": len(sections),
            "dry_run": dry_run,
            "path": path,
        }
    finally:
        await close_db(conn)
