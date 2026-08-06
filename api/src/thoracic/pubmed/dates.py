"""PubMed 检索日期换算:previous_us_eastern_day 与 edat_clause。

检索口径从 [epdat](电子出版日)改为 [edat](PubMed 入库日):
[edat] 的"一天"是美东日历日,封口后永不再变,所以单日检索即完整,
无需 [epdat] 那样回看两天补索引延迟。运行必须排在美东午夜翻页
(北京 12:00 夏令时 / 13:00 冬令时)之后,详见 PLAN.md 检索规则。
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
US_EASTERN = ZoneInfo("America/New_York")  # 自动处理夏令时
def previous_us_eastern_day(now: datetime | None = None) -> date:
    """美东时区"昨天" = 前一个已封口的完整 PubMed 入库日。"""
    if now is None:
        now = datetime.now(US_EASTERN)
    else:
        now = now.astimezone(US_EASTERN)
    return (now - timedelta(days=1)).date()
def edat_clause(target: date) -> str:
    """PubMed 入库日检索词:YYYY-MM-DD:YYYY-MM-DD[edat]"""
    s = target.isoformat()
    return f"{s}:{s}[edat]"
